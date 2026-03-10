from transformers import pipeline

MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"

def predict(text: str) -> dict:
    """Run sentiment classification on input text.
    
    Return a dict with 'label' (POSITIVE/NEGATIVE) and 'score' (float confidence).
    """
    result = classifier(text, truncation=True, max_length=512)[0]
    return {"label": result["label"], "score": round(result["score"], 4)}