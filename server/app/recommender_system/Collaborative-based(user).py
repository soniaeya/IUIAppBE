import numpy as np
import pandas as pd

# user–item matrix
def build_ui(ratings, user_col="userId", item_col="itemId", rating_col="rating"):
    R = ratings.pivot_table(index=user_col, columns=item_col, values=rating_col, aggfunc="mean")
    return R  # rows:users, cols:items

# Similarity Calculation
def cosine_overlap(u, v):
    mask = (~np.isnan(u)) & (~np.isnan(v))
    if mask.sum() == 0: return 0.0
    a, b = u[mask], v[mask]
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return 0.0 if den == 0 else float(np.dot(a, b) / den)

#user-user similarity
def user_sim_matrix(R, shrink=10.0):
    U = R.index.to_list() #user IDs
    X = R.to_numpy() #Ratings
    S = np.zeros((len(U), len(U)), dtype=float) #similarities
    obs = ~np.isnan(X) #if observed
    for i in range(len(U)):
        for j in range(i+1, len(U)):
            overlap = obs[i] & obs[j]
            n = int(overlap.sum())
            if n == 0:
                s = 0.0
            else:
                s = cosine_overlap(X[i], X[j]) * (n / (n + shrink))  # simple shrinkage
            S[i,j] = S[j,i] = s
    return pd.DataFrame(S, index=U, columns=U)

#predict rating
def predict_user_based(R, S, user, item, k=20):
    if user not in R.index or item not in R.columns: return None
    # neighbors who rated the item
    nbrs = R.index[~R[item].isna()]
    sims = S.loc[user, nbrs]
    sims = sims[sims > 0].sort_values(ascending=False).head(k)
    if sims.empty: return None

    nbr_r = R.loc[sims.index, item]
    nbr_mu = R.loc[sims.index].mean(axis=1, skipna=True)
    centered = nbr_r - nbr_mu
    w = sims.values
    m = ~centered.isna().values
    if m.sum() == 0: return None
    num = np.dot(w[m], centered.values[m])
    den = np.sum(np.abs(w[m]))
    if den == 0: return None

    mu_u = R.loc[user].mean(skipna=True)
    return float(mu_u + num / den)


#recommendation
def recommend_user_based(R, S, user, top_n=5, k=20):
    seen = R.loc[user].dropna().index if user in R.index else []
    preds = []
    for it in R.columns:
        if it in seen: continue
        p = predict_user_based(R, S, user, it, k=k)
        if p is not None:
            preds.append((it, p))
    recs = pd.DataFrame(preds, columns=["itemId", "pred"]).sort_values("pred", ascending=False)
    return recs.head(top_n).reset_index(drop=True)


if __name__ == "__main__":
    ratings = pd.DataFrame({
        "userId": [1,1,1,        2,2,2,     3,3,3,3,     4,4,4,     5,5,5],
        "itemId": [10,11,12,     10,13,14,  11,12,13,15, 10,12,14,  11,15,16],
        "rating": [4, 5, 3,      5, 2, 4,   4, 3, 2, 4,  4, 2, 5,   2, 5, 4]
    })
    R = build_ui(ratings)
    S = user_sim_matrix(R, shrink=10.0)
    recs = recommend_user_based(R, S, user=1, top_n=5, k=20)
    print("User 1 recommendations:")
    print(recs)