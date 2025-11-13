import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

#Content-based filtering
def build_content(items_df, text_col="features_text"):
    vec = TfidfVectorizer(stop_words="english")
    tfidf = vec.fit_transform(items_df[text_col].fillna(""))
    cos = cosine_similarity(tfidf, dense_output=False)
    return {"df": items_df.reset_index(drop=True), "cos": cos}

def content_scores_for_query(content, query_title, title_col="title"):
    df = content["df"]
    idx = df.index[df[title_col] == query_title]
    if len(idx) == 0: raise ValueError(f"Title not found: {query_title}")
    i = idx[0]
    scores = content["cos"][i].toarray().ravel()

    # normalizing scores [0,1]
    smin, smax = scores.min(), scores.max()
    if smax > smin: scores = (scores - smin) / (smax - smin)

    scores[i] = 0.0
    return pd.Series(scores, index=df.index)

# Collaborative Filtering
def build_ui(ratings, user_col="userId", item_col="itemId", rating_col="rating"):
    return ratings.pivot_table(index=user_col, columns=item_col, values=rating_col, aggfunc="mean")

def cosine_overlap(u, v):
    mask = (~np.isnan(u)) & (~np.isnan(v))
    if mask.sum() == 0: return 0.0
    a, b = u[mask], v[mask]
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return 0.0 if den == 0 else float(np.dot(a, b) / den)

def user_sim_matrix(R, shrink=10.0):
    U = R.index.to_list(); X = R.to_numpy(); obs = ~np.isnan(X)
    S = np.zeros((len(U), len(U)), dtype=float)
    for i in range(len(U)):
        for j in range(i+1, len(U)):
            overlap = obs[i] & obs[j]; n = int(overlap.sum())
            s = 0.0 if n == 0 else cosine_overlap(X[i], X[j]) * (n / (n + shrink))
            S[i,j] = S[j,i] = s
    return pd.DataFrame(S, index=U, columns=U)

def predict_user_based(R, S, user, item, k=20):
    if (user not in R.index) or (item not in R.columns): return np.nan
    nbrs = R.index[~R[item].isna()]
    sims = S.loc[user, nbrs]
    sims = sims[sims > 0].sort_values(ascending=False).head(k)
    if sims.empty: return np.nan
    nbr_r = R.loc[sims.index, item]
    nbr_mu = R.loc[sims.index].mean(axis=1, skipna=True)
    centered = nbr_r - nbr_mu
    w = sims.values; m = ~centered.isna().values
    if m.sum() == 0: return np.nan
    num = np.dot(w[m], centered.values[m]); den = np.sum(np.abs(w[m]))
    if den == 0: return np.nan
    mu_u = R.loc[user].mean(skipna=True)
    return float(mu_u + num / den)

def collab_scores_for_user(R, S, user):
    preds = {it: predict_user_based(R, S, user, it) for it in R.columns}
    s = pd.Series(preds, dtype=float)
    valid = s.dropna()
    if not valid.empty:
        smin, smax = valid.min(), valid.max()
        if smax > smin: s.loc[valid.index] = (valid - smin) / (smax - smin)
        else: s.loc[valid.index] = 0.5
    return s

# Combining them => making it hybrid
def hybrid_recommendations(content, R, S, user, query_title, alpha=0.5, top_n=5,
                           title_col="title", id_col="item_id"):
    df = content["df"]
    # Content-Based scores
    c_scores = content_scores_for_query(content, query_title, title_col=title_col)

    # Collab scores
    collab = collab_scores_for_user(R, S, user)
    collab = collab.reindex(df[id_col]).fillna(0.0).to_numpy()

    blended = alpha * c_scores.to_numpy() + (1 - alpha) * collab

    # exclude items the user already rated
    seen = set(R.loc[user].dropna().index) if user in R.index else set()
    mask = ~df[id_col].isin(seen)

    # rank
    idx = np.where(mask)[0]
    if len(idx) == 0: return pd.DataFrame(columns=[title_col, "hybrid"])
    take = min(top_n, len(idx))
    sub_scores = blended[idx]
    top_local = np.argpartition(-sub_scores, range(take))[:take]
    top_local = top_local[np.argsort(-sub_scores[top_local])]
    top_idx = idx[top_local]
    out = df.loc[top_idx, [id_col, title_col]].copy()
    out["content"] = c_scores.iloc[top_idx].to_numpy()
    out["collab"]  = collab[top_idx]
    out["hybrid"]  = blended[top_idx]
    out["alpha"]   = alpha
    return out.reset_index(drop=True)


if __name__ == "__main__":
    items_df = pd.DataFrame({
        "item_id": [10,11,12,13,14,15,16],
        "title": ["Inception","Interstellar","The Matrix","Arrival",
                  "Gravity","Blade Runner","Ex Machina"],
        "features_text": [
            "sci-fi dream heist mind-bending time layers subconscious nolanesque dicaprio",
            "sci-fi space time relativity wormhole mind-bending nolanesque mcconaughey",
            "sci-fi hacker simulation dystopia cyberpunk martial-arts reeves",
            "sci-fi linguistics aliens communication time nonlinear adams",
            "sci-fi space survival orbit debris tension bullock clooney",
            "drama dystopia replicants noir future blade-runner gosling ford villeneuve",
            "sci-fi ai android turing-test psychological minimal tech startup isaacson vikander"
        ]
    })


    ratings = pd.DataFrame({
        "userId": [1,1,1,  2,2,2,  3,3,3,3,  4,4,4,  5,5,5],
        "itemId": [10,11,12,  10,13,14,  11,12,13,15,  10,12,16,  14,15,16],
        "rating": [4,  5,  3,   5,  2,  4,   4,  3,  2,  5,   4,  2,  4,   4,  5,  4]
    })

    content = build_content(items_df)
    R = build_ui(ratings)
    S = user_sim_matrix(R, shrink=10.0)

    recs = hybrid_recommendations(content, R, S, user=1, query_title="Inception", alpha=0.6, top_n=5)
    print(recs)
