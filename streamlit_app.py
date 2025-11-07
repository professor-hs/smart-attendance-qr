import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests

st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")

# Global styles to match the reference theme
THEME_CSS = """
<style>
  .main, .stApp { background: #0b0f16; }
  .topbar { display:flex; justify-content:space-between; align-items:center; padding:10px 18px; background:#0b0f16; border-bottom:1px solid #222; }
  .brand { color:#f87171; font-weight:800; letter-spacing:2px; font-size:18px; }
  .user { color:#e5e7eb; font-weight:600; font-size:14px; }
  .hero { position:relative; border-radius:10px; overflow:hidden; margin:14px 0 18px; min-height:360px; }
  .hero::after { content:""; position:absolute; inset:0; background:linear-gradient(90deg, rgba(0,0,0,.75) 0%, rgba(0,0,0,.35) 55%, rgba(0,0,0,0) 100%);} 
  .hero-img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; filter:brightness(.85); }
  .hero-content { position:relative; z-index:2; padding:36px; max-width:760px; }
  .title { color:#fff; font-size:48px; line-height:1.1; font-weight:800; margin:0 0 10px; }
  .meta { color:#cbd5e1; font-size:14px; display:flex; gap:10px; align-items:center; margin-bottom:12px; }
  .badge { display:inline-block; padding:2px 8px; border-radius:6px; border:1px solid #3b3f46; color:#e5e7eb; font-size:12px; }
  .plot { color:#d1d5db; font-size:15px; line-height:1.6; }
  .section { color:#e5e7eb; font-weight:700; font-size:20px; margin:4px 0 10px; }
  .strip { display:grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap:14px; }
  .card { background:#111827; border:1px solid #1f2937; border-radius:10px; overflow:hidden; }
  .card img { width:100%; height:220px; object-fit:cover; display:block; }
  .card-body { padding:10px; }
  .card-title { color:#fff; font-weight:700; font-size:14px; margin:0 0 4px; }
  .card-sub { color:#9ca3af; font-size:12px; }
  .rec img { height:260px; }
  .rec .card-title { font-size:13px; }
</style>
"""

# Minimal demo dataset (replace with your CSV later)
# Added: year, actors, and poster placeholders
DATA = [
    {"title": "Inception", "year": 2010, "language": "English", "genres": "Action Sci-Fi Thriller", "actors": "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page", "overview": "A thief who steals corporate secrets through dream-sharing technology.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Inception"},
    {"title": "Interstellar", "year": 2014, "language": "English", "genres": "Adventure Drama Sci-Fi", "actors": "Matthew McConaughey, Anne Hathaway, Jessica Chastain", "overview": "A team travels through a wormhole in space in an attempt to ensure humanity's survival.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Interstellar"},
    {"title": "The Dark Knight", "year": 2008, "language": "English", "genres": "Action Crime Drama", "actors": "Christian Bale, Heath Ledger, Aaron Eckhart", "overview": "Batman faces the Joker, a criminal mastermind.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Dark+Knight"},
    {"title": "The Matrix", "year": 1999, "language": "English", "genres": "Action Sci-Fi", "actors": "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss", "overview": "A hacker discovers the reality is a simulation and joins a rebellion.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=The+Matrix"},
    {"title": "Avatar", "year": 2009, "language": "English", "genres": "Action Adventure Fantasy", "actors": "Sam Worthington, Zoe Saldana, Sigourney Weaver", "overview": "A paraplegic Marine dispatched to Pandora on a unique mission.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Avatar"},
    {"title": "Titanic", "year": 1997, "language": "English", "genres": "Drama Romance", "actors": "Leonardo DiCaprio, Kate Winslet, Billy Zane", "overview": "A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the Titanic.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Titanic"},
    {"title": "Vikram", "year": 2022, "language": "Tamil", "genres": "Action Thriller", "actors": "Kamal Haasan, Vijay Sethupathi, Fahadh Faasil", "overview": "A black-ops squad hunts down a ruthless drug network.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Vikram"},
    {"title": "RRR", "year": 2022, "language": "Telugu", "genres": "Action Drama", "actors": "N.T. Rama Rao Jr., Ram Charan, Alia Bhatt", "overview": "Two legendary revolutionaries and their journey far away from home.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=RRR"},
    {"title": "Drishyam", "year": 2013, "language": "Malayalam", "genres": "Crime Drama Thriller", "actors": "Mohanlal, Meena, Ansiba Hassan", "overview": "A man does everything he can to protect his family.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Drishyam"},
    {"title": "Kantara", "year": 2022, "language": "Kannada", "genres": "Action Drama Thriller", "actors": "Rishab Shetty, Kishore, Sapthami Gowda", "overview": "A clash between tradition and modernity in a village.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=Kantara"},
    {"title": "3 Idiots", "year": 2009, "language": "Hindi", "genres": "Comedy Drama", "actors": "Aamir Khan, Kareena Kapoor, R. Madhavan", "overview": "Two friends are searching for their long lost companion.", "poster": "https://placehold.co/300x450/0b1220/e5e7eb?text=3+Idiots"},
]

df = pd.DataFrame(DATA)

st.markdown(THEME_CSS, unsafe_allow_html=True)
st.markdown('<div class="topbar"><div class="brand">JD</div><div class="user">JD</div></div>', unsafe_allow_html=True)
st.title(" ")

# Combine text features for similarity
corpus = (df["title"] + " " + df["genres"] + " " + df["actors"] + " " + df["overview"]).fillna("")
vectorizer = TfidfVectorizer(stop_words="english")
X = vectorizer.fit_transform(corpus)

# Sidebar controls (Step 1)
with st.sidebar:
    st.header("Step 1 · Pick timeframe and genres")
    # Timeline first
    year_min, year_max = int(df["year"].min()), int(df["year"].max())
    year_range = st.slider("Year range", min_value=year_min, max_value=year_max, value=(year_min, year_max))

    # Genres multiselect
    all_genres = sorted({g.strip() for row in df["genres"] for g in row.split()})
    genres = st.multiselect("Genres", options=all_genres)

    st.markdown("---")
    st.subheader("Step 2 · Narrow further (optional)")
    # Languages (optional)
    all_langs = sorted(df["language"].unique().tolist())
    languages = st.multiselect("Languages", options=all_langs)
    # Actors (optional)
    all_actors = sorted({a.strip() for row in df["actors"] for a in row.split(",")})
    actors = st.multiselect("Actors", options=all_actors)

    st.markdown("---")
    st.subheader("Preferences")
    top_k = st.slider("Recommendations", 3, 12, 6)

    st.markdown("---")
    st.subheader("AI details (OMDb)")
    omdb_key = st.text_input("OMDb API Key (optional)", type="password")

# Apply filters based on Step 1/2
mask = (df["year"].between(year_range[0], year_range[1]))
if genres:
    mask &= df["genres"].apply(lambda s: all(g in s for g in genres))
if languages:
    mask &= df["language"].isin(languages)
if actors:
    mask &= df["actors"].apply(lambda s: any(a in s for a in actors))

# Available movies grid (Step 3)
avail = df[mask].reset_index(drop=False)  # keep original index in 'index'
st.markdown('<div class="section">Available Movies</div>', unsafe_allow_html=True)
grid = []
for _, r in avail.iterrows():
    card = f"""
    <div class='card rec'>
      <img src='{r['poster']}' alt='{r['title']}'>
      <div class='card-body'>
        <div class='card-title'>{r['title']}</div>
        <div class='card-sub'>{r['year']} • {r['language']} • {r['genres']}</div>
      </div>
    </div>
    """
    grid.append(card)
st.markdown(f"<div class='strip'>{''.join(grid)}</div>", unsafe_allow_html=True)

# Selection of anchor title from filtered list (Step 4)
titles_filtered = avail["title"].tolist() or df["title"].tolist()
selected = st.selectbox("Select a movie to view details", titles_filtered)
idx = df.index[df["title"] == selected][0]
sims = cosine_similarity(X[idx], X).ravel()

# Rank recommendations within filters if possible, else global
order = sims.argsort()[::-1]
order = [i for i in order if i != idx and (mask.iloc[i] if i < len(mask) else True)]
order = order[:top_k]

def hero_section(row, rating=None):
    bg = row["poster"].replace("300x450", "1200x600") if isinstance(row["poster"], str) else "https://placehold.co/1200x600/0b1220/e5e7eb?text=Poster"
    meta_bits = [str(int(row["year"])) if not pd.isna(row["year"]) else "" , row["language"], row["genres"]]
    meta_html = " | ".join([m for m in meta_bits if m])
    if rating:
        meta_html += f" | ⭐ {rating} IMDb"
    html = f"""
    <div class='hero'>
      <img class='hero-img' src='{bg}' alt='bg'>
      <div class='hero-content'>
        <div class='title'>{row['title']}</div>
        <div class='meta'><span class='badge'>{meta_html}</span></div>
        <div class='plot'>{row['overview']}</div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def omdb_lookup(title, year=None, apikey=None):
    if not apikey:
        return {}
    try:
        params = {"t": title, "apikey": apikey}
        if year:
            params["y"] = str(year)
        r = requests.get("https://www.omdbapi.com/", params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data.get("Response") == "True":
                return data
    except Exception:
        pass
    return {}

anchor = df.loc[idx]
om_anchor = omdb_lookup(anchor["title"], int(anchor["year"]) if not pd.isna(anchor["year"]) else None, omdb_key)
rating_anchor = om_anchor.get("imdbRating") if om_anchor.get("imdbRating") and om_anchor.get("imdbRating") != "N/A" else None
hero_section(anchor, rating_anchor)

# Cast section
st.markdown('<div class="section">Cast</div>', unsafe_allow_html=True)
cast_list = [a.strip() for a in anchor["actors"].split(",")]
cast_cards = []
for name in cast_list:
    img = f"https://placehold.co/400x550/0b1220/e5e7eb?text={name.replace(' ', '+')}"
    card = f"""
    <div class='card'>
      <img src='{img}' alt='{name}'>
      <div class='card-body'>
        <div class='card-title'>{name}</div>
        <div class='card-sub'>Cast</div>
      </div>
    </div>
    """
    cast_cards.append(card)
st.markdown(f"<div class='strip'>{''.join(cast_cards)}</div>", unsafe_allow_html=True)

# Recommendations section
st.markdown('<div class="section" style="margin-top:14px">Movie Recommendations</div>', unsafe_allow_html=True)
rec_cards = []
for rec_idx in order:
    row = df.loc[rec_idx]
    om = omdb_lookup(row["title"], int(row["year"]) if not pd.isna(row["year"]) else None, omdb_key)
    poster = om.get("Poster") if om.get("Poster") and om.get("Poster") != "N/A" else row["poster"]
    title_line = f"{row['title']}"
    card = f"""
    <div class='card rec'>
      <img src='{poster}' alt='{title_line}'>
      <div class='card-body'>
        <div class='card-title'>{title_line}</div>
        <div class='card-sub'>{row['genres']}</div>
      </div>
    </div>
    """
    rec_cards.append(card)
st.markdown(f"<div class='strip'>{''.join(rec_cards)}</div>", unsafe_allow_html=True)

# Minor alterations section
st.markdown("---")
with st.expander("About this demo"):
    st.write(
        "This is a minimal TF-IDF + cosine similarity recommender with posters and filters. "
        "Swap DATA with your dataset (including year, actors, poster URL), or load a CSV and recompute the vectorizer.")
