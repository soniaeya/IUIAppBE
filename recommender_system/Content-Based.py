import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def build_content_model(items_df, text_col="features_text"):
    #Tokenizing
    vec = TfidfVectorizer(stop_words="english", token_pattern=r"(?u)\b[\w:-]+\b")
    tfidf = vec.fit_transform(items_df[text_col].fillna(""))
    #Similarity Calculation
    cos = cosine_similarity(tfidf, dense_output=False)
    return {"vec": vec, "tfidf": tfidf, "cos": cos, "df": items_df.reset_index(drop=True)}

def recommend_similar_items(model, query_title, top_n=5, title_col="title"):
    df = model["df"]
    idx = df.index[df[title_col] == query_title]
    if len(idx) == 0:
        raise ValueError(f"Title not found: {query_title}")
    i = idx[0]
    sims = model["cos"][i].toarray().ravel()
    sims[i] = -np.inf  # exclude the query item
    n = min(top_n, len(sims) - 1)
    top = np.argpartition(-sims, range(n))[:n]
    top = top[np.argsort(-sims[top])]
    out = df.loc[top, [title_col]].copy()
    out["score"] = sims[top]
    return out.reset_index(drop=True)


if __name__ == "__main__":
    items_df = pd.DataFrame({
        "item_id": [1, 2, 3, 4],
        "title": ["Inception", "Interstellar", "The Matrix", "Arrival"],
        "features_text": [
            "sci-fi dream heist mind-bending time layers subconscious nolanesque dicaprio",
            "sci-fi space time relativity wormhole mind-bending nolanesque mcconaughey",
            "sci-fi hacker simulation dream time dystopia cyberpunk martial-arts reeves",
            "sci-fi linguistics aliens communication time nonlinear adams"
        ]
    })
    model = build_content_model(items_df)
    print(recommend_similar_items(model, "Inception", top_n=3))
