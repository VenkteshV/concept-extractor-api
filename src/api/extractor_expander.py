from typing import List,Any
from api.models import LearningContent
from fastapi import Header, APIRouter
from main.extract_concepts import extract_concepts, expand_concepts

extractor_expander = APIRouter()

@extractor_expander.post('/extract',response_model=List[Any])
async def get_paraphrase(payload: LearningContent):
    return extract_concepts(payload.content)

@extractor_expander.post('/expand',response_model=List[Any])
async def get_paraphrase(payload: LearningContent):
    return expand_concepts(payload.content)