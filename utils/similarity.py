from sentence_transformers import SentenceTransformer, util

# Load once (fast after first run)
model = SentenceTransformer("all-MiniLM-L6-v2")

SIMILARITY_THRESHOLD = 0.72  # tweak later


def is_similar(text1, text2):
    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)

    score = util.cos_sim(emb1, emb2).item()
    return score >= SIMILARITY_THRESHOLD, score