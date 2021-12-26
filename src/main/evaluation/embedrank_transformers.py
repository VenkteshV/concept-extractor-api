import os

from keep.utility import getlanguage, CreateKeywordsFolder, LoadFiles, Convert2TrecEval
from pke import compute_lda_model
from helpers import read_json
from main.keyword_extraction.helpers import init_keyword_extractor, init_nlp
import main.extraction.extractor as extractors
from gensim.utils import simple_preprocess
from gensim import corpora, models
import nltk
from gensim.parsing.preprocessing import STOPWORDS
from sklearn.decomposition import LatentDirichletAllocation
from pke.base import LoadFile
import gensim
import gzip 
import pickle

import os

dir_path = os.path.dirname(os.path.realpath(__file__))


class CoTagRankUSE(object):
    def __init__(self, numOfKeywords, pathData, dataset_name, normalization):
        super().__init__()
        self.__lan = getlanguage(pathData + "/Datasets/" + dataset_name)
        self.__numOfKeywords = numOfKeywords
        self.__dataset_name = dataset_name
        self.__normalization = normalization
        self.__pathData = pathData
        self._lda_model = self.__pathData + "/Models/Unsupervised/lda/" + self.__dataset_name + '_lda.gz'
        self.__pathToDFFile = self.__pathData + "/Models/Unsupervised/dfs/" + self.__dataset_name + '_dfs.gz'
        self.__pathToDatasetName = self.__pathData + "/Datasets/" + self.__dataset_name
        self.__keywordsPath = f"{self.__pathData}/Keywords/{self.__class__.__name__}/{self.__dataset_name}"
        self.__outputPath = self.__pathData + "/conversor/output/"
        self.__algorithmName = f"{self.__class__.__name__}"
        self.phraseextractor = extractors.PhraseExtractor(grammar =  "GRAMMAR1",np_method="GRAMMAR",
         np_tags = "NLTK",
         stopwords = "NLTK", nlp = init_nlp({"name":"spacy" , "model_name": "en_core_web_sm"}))

        self.model = init_keyword_extractor(read_json(dir_path+'/config/conceptrank_USE.json'))

    def LoadDatasetFiles(self):
        # Gets all files within the dataset fold
        listFile = LoadFiles(self.__pathToDatasetName + '/docsutf8/*')
        print(f"\ndatasetID = {self.__dataset_name}; Number of Files = "
              f"{len(listFile)}; Language of the Dataset = {self.__lan}")
        return listFile

    def CreateKeywordsOutputFolder(self):
        # Set the folder where keywords are going to be saved
        CreateKeywordsFolder(self.__keywordsPath)


    def load_lda_model(self):
         model = LatentDirichletAllocation()
         with gzip.open(self._lda_model, 'rb') as f:
            (dictionary,
             model.components_,
             model.exp_dirichlet_component_,
             model.doc_topic_prior_) = pickle.load(f)
         return model, dictionary
    def runSingleDoc(self, doc, lda_model, dictionary, lists, text = None, highlight=None, expand=False):
        try:
            # read raw document
            if text:
                doc_text = text
                doc=text
            else:
                with open(doc, 'r') as doc_reader:
                    doc_text = doc_reader.read()
            document = LoadFile()
            document.load_document(input=doc,
                language='en',
                normalization='stemming')
            texts = []
            text = []
            if self.__dataset_name == "SemEval2010":
                if len(doc_text.split("INTRODUCTION")) > 1:
                    doc_text_abstract = doc_text.split("INTRODUCTION")[0]

                    doc_text_intro_partial = " ".join(doc_text.split("INTRODUCTION")[1].split(" ")[:100])
                else:
                    doc_text_abstract = " ".join(doc_text.split(" ")[:400])
                    doc_text_intro_partial = " "
                doc_text = doc_text_abstract+" "+doc_text_intro_partial
            if self.__dataset_name == "NLM500":
                doc_text_abstract_intro = " ".join(doc_text.split(" ")[:200])
                doc_text = doc_text_abstract_intro
                # print(doc_text)
            # loop through sentences
            for sentence in document.sentences:
                # get the tokens (stems) from the sentence if they are not
                # punctuation marks 
                text.extend([sentence.stems[i] for i in range(sentence.length)
                            if sentence.pos[i] != 'PUNCT' and
                            sentence.pos[i].isalpha()])

            # add the document to the texts container
            texts.append(' '.join(text))
            # extract keywords
            if expand:
                keywords, phrase_with_positions, color_map = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRank", lists=lists, highlight=highlight, expand=expand)
            else:
                keywords, phrase_with_positions = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRank", lists=lists, highlight=highlight, expand=expand)

            concepts = [(keyword, score) for score, keyword in keywords if keyword]
        except e:
            concepts = []
        # print("concepts**", concepts)
        if expand:
            return concepts, phrase_with_positions,color_map
        else:
            return concepts, phrase_with_positions

    def runMultipleDocs(self, listOfDocs, lda_model, dictionary, lists, expand):
        self.CreateKeywordsOutputFolder()

        for j, doc in enumerate(listOfDocs):
            # docID keeps the name of the file (without the extension)
            docID = '.'.join(os.path.basename(doc).split('.')[0:-1])
            # print("docID", docID)
            if expand:
                keywords, phrase_with_positions, color_map = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            else:
                keywords, phrase_with_positions = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            # print("keywords", keywords)
            # Save the keywords; score (on Algorithms/NameOfAlg/Keywords/NameOfDataset
            concepts_prev = []
            with open(os.path.join(self.__keywordsPath, docID), 'w', encoding="utf-8") as out:
                for (key, score) in keywords:
                    if key not in concepts_prev:
                        out.write(f'{key} {score}\n')
                        concepts_prev.append(key)


            # Track the status of the task
            print(f"\rFile: {j + 1}/{len(listOfDocs)}", end='')

        print(f"\n100% of the Extraction Concluded")
        return phrase_with_positions

    def ExtractKeyphrases(self, text=None, highlight=None, expand=False):
        # print(f"\n------------------------------Compute DF--------------------------")
        # self.ComputeDocumentFrequency()
        lda_model, dictionary = self.load_lda_model()
        if text:
            return self.runSingleDoc(None, lda_model, dictionary, None, text, highlight, expand)

        print(f"\n\n-----------------Extract Keyphrases--------------------------")
        listOfDocs = self.LoadDatasetFiles()
        if self.__dataset_name == "KhanAcad":
        # or self.__dataset_name == "ExtraMarks":
            with open('evaluation/en_kp_list', 'r', encoding='utf-8') as f:
                lists = f.read().split('\n')
                print('load kp_list done.')
        else:
            lists = None

        self.runMultipleDocs(listOfDocs, lda_model, dictionary, lists, expand=expand)

    def Convert2Trec_Eval(self, EvaluationStemming=False):
        Convert2TrecEval(self.__pathToDatasetName, EvaluationStemming, self.__outputPath, self.__keywordsPath,
                         self.__dataset_name, self.__algorithmName)

class CoTagRankSentenceUSE(object):
    def __init__(self, numOfKeywords, pathData, dataset_name, normalization):
        super().__init__()
        self.__lan = getlanguage(pathData + "/Datasets/" + dataset_name)
        self.__numOfKeywords = numOfKeywords
        self.__dataset_name = dataset_name
        self.__normalization = normalization
        self.__pathData = pathData
        self._lda_model = self.__pathData + "/Models/Unsupervised/lda/" + self.__dataset_name + '_lda.gz'

        self.__pathToDFFile = self.__pathData + "/Models/Unsupervised/dfs/" + self.__dataset_name + '_dfs.gz'
        self.__pathToDatasetName = self.__pathData + "/Datasets/" + self.__dataset_name
        self.__keywordsPath = f"{self.__pathData}/Keywords/{self.__class__.__name__}/{self.__dataset_name}"
        self.__outputPath = self.__pathData + "/conversor/output/"
        self.__algorithmName = f"{self.__class__.__name__}"
        self.phraseextractor = extractors.PhraseExtractor(grammar =  "GRAMMAR1",np_method="GRAMMAR",
         np_tags = "NLTK",
         stopwords = "NLTK", nlp = init_nlp({"name":"spacy" , "model_name": "en_core_web_sm"}))

        self.model = init_keyword_extractor(read_json(dir_path+'/config/conceptrank_sentence_use.json'))

    def LoadDatasetFiles(self):
        # Gets all files within the dataset fold
        listFile = LoadFiles(self.__pathToDatasetName + '/docsutf8/*')
        print(f"\ndatasetID = {self.__dataset_name}; Number of Files = "
              f"{len(listFile)}; Language of the Dataset = {self.__lan}")
        return listFile

    def CreateKeywordsOutputFolder(self):
        # Set the folder where keywords are going to be saved
        CreateKeywordsFolder(self.__keywordsPath)


    def load_lda_model(self):
         model = LatentDirichletAllocation()
         with gzip.open(self._lda_model, 'rb') as f:
            (dictionary,
             model.components_,
             model.exp_dirichlet_component_,
             model.doc_topic_prior_) = pickle.load(f)
         return model, dictionary
    def runSingleDoc(self, doc, lda_model, dictionary, lists, text = None, highlight=None, expand=False):
        try:
            # read raw document
            if text:
                doc_text = text
                doc=text
            else:
                with open(doc, 'r') as doc_reader:
                    doc_text = doc_reader.read()
            document = LoadFile()
            document.load_document(input=doc,
                language='en',
                normalization='stemming')
            texts = []
            text = []
            if self.__dataset_name == "SemEval2010":
                if len(doc_text.split("INTRODUCTION")) > 1:
                    doc_text_abstract = doc_text.split("INTRODUCTION")[0]

                    doc_text_intro_partial = " ".join(doc_text.split("INTRODUCTION")[1].split(" ")[:100])
                else:
                    doc_text_abstract = " ".join(doc_text.split(" ")[:400])
                    doc_text_intro_partial = " "
                doc_text = doc_text_abstract+" "+doc_text_intro_partial
            if self.__dataset_name == "NLM500":
                doc_text_abstract_intro = " ".join(doc_text.split(" ")[:200])
                doc_text = doc_text_abstract_intro
                # print(doc_text)
            # loop through sentences
            for sentence in document.sentences:
                # get the tokens (stems) from the sentence if they are not
                # punctuation marks 
                text.extend([sentence.stems[i] for i in range(sentence.length)
                            if sentence.pos[i] != 'PUNCT' and
                            sentence.pos[i].isalpha()])

            # add the document to the texts container
            texts.append(' '.join(text))
            # extract keywords
            if expand:
                keywords, phrase_with_positions, color_map = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRankSentenceUSE", lists=lists, highlight=highlight, expand=expand)
            else:
                keywords, phrase_with_positions = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRankSentenceUSE", lists=lists, highlight=highlight, expand=expand)

            concepts = [(keyword, score) for score, keyword in keywords if keyword]
        except e:
            concepts = []
        # print("concepts**", concepts)
        if expand:
            return concepts, phrase_with_positions,color_map
        else:
            return concepts, phrase_with_positions

    def runMultipleDocs(self, listOfDocs, lda_model, dictionary, lists, expand):
        self.CreateKeywordsOutputFolder()

        for j, doc in enumerate(listOfDocs):
            # docID keeps the name of the file (without the extension)
            docID = '.'.join(os.path.basename(doc).split('.')[0:-1])
            # print("docID", docID)
            if expand:
                keywords, phrase_with_positions, color_map = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            else:
                keywords, phrase_with_positions = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            # print("keywords", keywords)
            # Save the keywords; score (on Algorithms/NameOfAlg/Keywords/NameOfDataset
            concepts_prev = []
            with open(os.path.join(self.__keywordsPath, docID), 'w', encoding="utf-8") as out:
                for (key, score) in keywords:
                    if key not in concepts_prev:
                        out.write(f'{key} {score}\n')
                        concepts_prev.append(key)


            # Track the status of the task
            print(f"\rFile: {j + 1}/{len(listOfDocs)}", end='')

        print(f"\n100% of the Extraction Concluded")
        return phrase_with_positions

    def ExtractKeyphrases(self, text=None, highlight=None, expand=False):
        # print(f"\n------------------------------Compute DF--------------------------")
        # self.ComputeDocumentFrequency()
        lda_model, dictionary = self.load_lda_model()
        if text:
            return self.runSingleDoc(None, lda_model, dictionary, None, text, highlight, expand)

        print(f"\n\n-----------------Extract Keyphrases--------------------------")
        listOfDocs = self.LoadDatasetFiles()
        if self.__dataset_name == "KhanAcad":
        # or self.__dataset_name == "ExtraMarks":
            with open('evaluation/en_kp_list', 'r', encoding='utf-8') as f:
                lists = f.read().split('\n')
                print('load kp_list done.')
        else:
            lists = None

        self.runMultipleDocs(listOfDocs, lda_model, dictionary, lists, expand=expand)

    def Convert2Trec_Eval(self, EvaluationStemming=False):
        Convert2TrecEval(self.__pathToDatasetName, EvaluationStemming, self.__outputPath, self.__keywordsPath,
                         self.__dataset_name, self.__algorithmName)
class CoTagRankWindow(object):
    def __init__(self, numOfKeywords, pathData, dataset_name, normalization):
        super().__init__()
        self.__lan = getlanguage(pathData + "/Datasets/" + dataset_name)
        self.__numOfKeywords = numOfKeywords
        self.__dataset_name = dataset_name
        self.__normalization = normalization
        self.__pathData = pathData
        self._lda_model = self.__pathData + "/Models/Unsupervised/lda/" + self.__dataset_name + '_lda.gz'
        self.__pathToDFFile = self.__pathData + "/Models/Unsupervised/dfs/" + self.__dataset_name + '_dfs.gz'
        self.__pathToDatasetName = self.__pathData + "/Datasets/" + self.__dataset_name
        self.__keywordsPath = f"{self.__pathData}/Keywords/{self.__class__.__name__}/{self.__dataset_name}"
        self.__outputPath = self.__pathData + "/conversor/output/"
        self.__algorithmName = f"{self.__class__.__name__}"
        self.phraseextractor = extractors.PhraseExtractor(grammar =  "GRAMMAR1",np_method="GRAMMAR",
         np_tags = "NLTK",
         stopwords = "NLTK", nlp = init_nlp({"name":"spacy" , "model_name": "en_core_web_sm"}))

        self.model = init_keyword_extractor(read_json(dir_path+'/config/conceptrank_window.json'))

    def LoadDatasetFiles(self):
        # Gets all files within the dataset fold
        listFile = LoadFiles(self.__pathToDatasetName + '/docsutf8/*')
        print(f"\ndatasetID = {self.__dataset_name}; Number of Files = "
              f"{len(listFile)}; Language of the Dataset = {self.__lan}")
        return listFile

    def CreateKeywordsOutputFolder(self):
        # Set the folder where keywords are going to be saved
        CreateKeywordsFolder(self.__keywordsPath)


    def load_lda_model(self):
         model = LatentDirichletAllocation()
         with gzip.open(self._lda_model, 'rb') as f:
            (dictionary,
             model.components_,
             model.exp_dirichlet_component_,
             model.doc_topic_prior_) = pickle.load(f)
         return model, dictionary
    def runSingleDoc(self, doc, lda_model, dictionary, lists, text = None, highlight=None, expand=False):
        try:
            # read raw document
            if text:
                doc_text = text
                doc=text
            else:
                with open(doc, 'r') as doc_reader:
                    doc_text = doc_reader.read()
            document = LoadFile()
            if self.__dataset_name == "SemEval2010":
                if len(doc_text.split("INTRODUCTION")) > 1:
                    doc_text_abstract = doc_text.split("INTRODUCTION")[0]

                    doc_text_intro_partial = " ".join(doc_text.split("INTRODUCTION")[1].split(" ")[:150])
                else:
                    doc_text_abstract = " ".join(doc_text.split(" ")[:400])
                    doc_text_intro_partial = " "
                doc_text = doc_text_abstract+" "+doc_text_intro_partial
            if self.__dataset_name == "NLM500":
                doc_text_abstract_intro = " ".join(doc_text.split(" ")[:400])
                doc_text = doc_text_abstract_intro
            document.load_document(input=doc,
                language='en',
                normalization='stemming')
            texts = []
            text = []

            # loop through sentences
            for sentence in document.sentences:
                # get the tokens (stems) from the sentence if they are not
                # punctuation marks 
                text.extend([sentence.stems[i] for i in range(sentence.length)
                            if sentence.pos[i] != 'PUNCT' and
                            sentence.pos[i].isalpha()])

            # add the document to the texts container
            texts.append(' '.join(text))
            # extract keywords
            if expand:
                keywords, phrase_with_positions, color_map = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRankWindow", lists=lists, highlight=highlight, expand=expand)
            else:
                keywords, phrase_with_positions = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRankWindow", lists=lists, highlight=highlight, expand=expand)

            concepts = [(keyword, score) for score, keyword in keywords if keyword]
        except e:
            concepts = []
        # print("concepts**", concepts)
        if expand:
            return concepts, phrase_with_positions,color_map
        else:
            return concepts, phrase_with_positions

    def runMultipleDocs(self, listOfDocs, lda_model, dictionary, lists, expand):
        self.CreateKeywordsOutputFolder()

        for j, doc in enumerate(listOfDocs):
            # docID keeps the name of the file (without the extension)
            docID = '.'.join(os.path.basename(doc).split('.')[0:-1])
            # print("docID", docID)
            keywords, phrase_with_positions = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            # print("keywords", keywords)
            # Save the keywords; score (on Algorithms/NameOfAlg/Keywords/NameOfDataset
            concepts_prev = []
            with open(os.path.join(self.__keywordsPath, docID), 'w', encoding="utf-8") as out:
                for (key, score) in keywords:
                    if key not in concepts_prev:
                        out.write(f'{key} {score}\n')
                        concepts_prev.append(key)


            # Track the status of the task
            print(f"\rFile: {j + 1}/{len(listOfDocs)}", end='')

        print(f"\n100% of the Extraction Concluded")
        return phrase_with_positions

    def ExtractKeyphrases(self, text=None, highlight=None, expand=False):
        # print(f"\n------------------------------Compute DF--------------------------")
        # self.ComputeDocumentFrequency()
        lda_model, dictionary = self.load_lda_model()
        if text:
            return self.runSingleDoc(None, lda_model, dictionary, None, text, highlight, expand)

        print(f"\n\n-----------------Extract Keyphrases--------------------------")
        listOfDocs = self.LoadDatasetFiles()
        if self.__dataset_name == "KhanAcad":
        # or self.__dataset_name == "ExtraMarks":
            with open('evaluation/en_kp_list', 'r', encoding='utf-8') as f:
                lists = f.read().split('\n')
                print('load kp_list done.')
        else:
            lists = None

        self.runMultipleDocs(listOfDocs, lda_model, dictionary, lists, expand=expand)

    def Convert2Trec_Eval(self, EvaluationStemming=False):
        Convert2TrecEval(self.__pathToDatasetName, EvaluationStemming, self.__outputPath, self.__keywordsPath,
                         self.__dataset_name, self.__algorithmName)



class CoTagRankPositional(object):
    def __init__(self, numOfKeywords, pathData, dataset_name, normalization):
        super().__init__()
        self.__lan = getlanguage(pathData + "/Datasets/" + dataset_name)
        self.__numOfKeywords = numOfKeywords
        self.__dataset_name = dataset_name
        self.__normalization = normalization
        self.__pathData = pathData
        self._lda_model = self.__pathData + "/Models/Unsupervised/lda/" + self.__dataset_name + '_lda.gz'
        self.__pathToDFFile = self.__pathData + "/Models/Unsupervised/dfs/" + self.__dataset_name + '_dfs.gz'
        self.__pathToDatasetName = self.__pathData + "/Datasets/" + self.__dataset_name
        self.__keywordsPath = f"{self.__pathData}/Keywords/{self.__class__.__name__}/{self.__dataset_name}"
        self.__outputPath = self.__pathData + "/conversor/output/"
        self.__algorithmName = f"{self.__class__.__name__}"
        self.phraseextractor = extractors.PhraseExtractor(grammar =  "GRAMMAR1",np_method="GRAMMAR",
         np_tags = "NLTK",
         stopwords = "NLTK", nlp = init_nlp({"name":"spacy" , "model_name": "en_core_web_sm"}))

        self.model = init_keyword_extractor(read_json(dir_path+'/config/CotagRank_positional.json'))

    def LoadDatasetFiles(self):
        # Gets all files within the dataset fold
        listFile = LoadFiles(self.__pathToDatasetName + '/docsutf8/*')
        print(f"\ndatasetID = {self.__dataset_name}; Number of Files = "
              f"{len(listFile)}; Language of the Dataset = {self.__lan}")
        return listFile

    def CreateKeywordsOutputFolder(self):
        # Set the folder where keywords are going to be saved
        CreateKeywordsFolder(self.__keywordsPath)


    def load_lda_model(self):
         model = LatentDirichletAllocation()
         with gzip.open(self._lda_model, 'rb') as f:
            (dictionary,
             model.components_,
             model.exp_dirichlet_component_,
             model.doc_topic_prior_) = pickle.load(f)
         return model, dictionary
    def runSingleDoc(self, doc, lda_model, dictionary, lists, text = None, highlight=None, expand=False):
        try:
            # read raw document
            if text:
                doc_text = text
                doc=text
            else:
                with open(doc, 'r') as doc_reader:
                    doc_text = doc_reader.read()
            document = LoadFile()
            if self.__dataset_name == "SemEval2010":
                if len(doc_text.split("INTRODUCTION")) > 1:
                    doc_text_abstract = doc_text.split("INTRODUCTION")[0]

                    doc_text_intro_partial = " ".join(doc_text.split("INTRODUCTION")[1].split(" ")[:150])
                else:
                    doc_text_abstract = " ".join(doc_text.split(" ")[:400])
                    doc_text_intro_partial = " "
                doc_text = doc_text_abstract+" "+doc_text_intro_partial
            if self.__dataset_name == "NLM500":
                doc_text_abstract_intro = " ".join(doc_text.split(" ")[:200])
                doc_text = doc_text_abstract_intro
                # print(doc_text)

            document.load_document(input=doc,
                language='en',
                normalization='stemming')
            texts = []
            text = []

            # loop through sentences
            for sentence in document.sentences:
                # get the tokens (stems) from the sentence if they are not
                # punctuation marks 
                text.extend([sentence.stems[i] for i in range(sentence.length)
                            if sentence.pos[i] != 'PUNCT' and
                            sentence.pos[i].isalpha()])

            # add the document to the texts container
            texts.append(' '.join(text))
            # extract keywords
            if expand:
                keywords, phrase_with_positions, color_map = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRank", lists=lists, highlight=highlight, expand=expand)
            else:
                keywords, phrase_with_positions = self.model.run(doc_text, texts, lda_model, dictionary, method = "CoTagRank", lists=lists, highlight=highlight, expand=expand)

            concepts = [(keyword, score) for score, keyword in keywords if keyword]
        except e:
            concepts = []
        # print("concepts**", concepts)
        if expand:
            return concepts, phrase_with_positions,color_map
        else:
            return concepts, phrase_with_positions

    def runMultipleDocs(self, listOfDocs, lda_model, dictionary, lists, expand):
        self.CreateKeywordsOutputFolder()

        for j, doc in enumerate(listOfDocs):
            # docID keeps the name of the file (without the extension)
            docID = '.'.join(os.path.basename(doc).split('.')[0:-1])
            # print("docID", docID)
            if expand:
                keywords, phrase_with_positions, color_map = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            else:
                keywords, phrase_with_positions = self.runSingleDoc(doc, lda_model, dictionary, lists, expand=expand)
            # print("keywords", keywords)
            # Save the keywords; score (on Algorithms/NameOfAlg/Keywords/NameOfDataset
            concepts_prev = []
            with open(os.path.join(self.__keywordsPath, docID), 'w', encoding="utf-8") as out:
                for (key, score) in keywords:
                    if key not in concepts_prev:
                        out.write(f'{key} {score}\n')
                        concepts_prev.append(key)


            # Track the status of the task
            print(f"\rFile: {j + 1}/{len(listOfDocs)}", end='')

        print(f"\n100% of the Extraction Concluded")
        return phrase_with_positions

    def ExtractKeyphrases(self, text=None, highlight=None, expand=False):
        # print(f"\n------------------------------Compute DF--------------------------")
        # self.ComputeDocumentFrequency()
        lda_model, dictionary = self.load_lda_model()
        if text:
            return self.runSingleDoc(None, lda_model, dictionary, None, text, highlight, expand)

        print(f"\n\n-----------------Extract Keyphrases--------------------------")
        listOfDocs = self.LoadDatasetFiles()
        if self.__dataset_name == "KhanAcad":
        # or self.__dataset_name == "ExtraMarks":
            with open('evaluation/en_kp_list', 'r', encoding='utf-8') as f:
                lists = f.read().split('\n')
                print('load kp_list done.')
        else:
            lists = None

        self.runMultipleDocs(listOfDocs, lda_model, dictionary, lists, expand=expand)

    def Convert2Trec_Eval(self, EvaluationStemming=False):
        Convert2TrecEval(self.__pathToDatasetName, EvaluationStemming, self.__outputPath, self.__keywordsPath,
                         self.__dataset_name, self.__algorithmName)
