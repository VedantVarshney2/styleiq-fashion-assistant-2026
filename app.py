
import os, re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="StyleIQ | Fashion Assistant", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded")

# ---------- Theme ----------
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1450px;}
.hero {padding: 1.35rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg,#171923,#343b55); color: white; margin-bottom: 1rem;}
.hero h1 {font-size: 2.15rem; margin: 0 0 .25rem 0;}
.hero p {color:#e2e6f0; margin:0;}
.small-muted {color: #8992a5; font-size:.9rem;}
div[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.22); padding:14px; border-radius:14px;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    path = "fashion_dataset_1000.csv"
    if not os.path.exists(path):
        raise FileNotFoundError("Place fashion_dataset_1000.csv in the same folder as app.py.")
    d = pd.read_csv(path)
    required = ["Product_ID","Category","Subcategory","Gender","Color","Size","Brand","Price_INR","Rating"]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError("Dataset is missing columns: " + ", ".join(missing))
    d["Price_INR"] = pd.to_numeric(d["Price_INR"], errors="coerce")
    d["Rating"] = pd.to_numeric(d["Rating"], errors="coerce")
    return d.dropna(subset=["Product_ID","Price_INR","Rating"]).copy()

df = load_data()

def inr(x):
    return f"₹{x:,.0f}"

def product_table(d):
    out = d[["Product_ID","Subcategory","Category","Gender","Color","Size","Brand","Price_INR","Rating"]].copy()
    out["Price_INR"] = out["Price_INR"].map(inr)
    out["Rating"] = out["Rating"].map(lambda x: f"⭐ {x:.1f}")
    return out

def parse_chat_query(query):
    q = query.lower().strip()
    result = df.copy()
    applied = []

    if any(x in q for x in ["help", "what can you do", "suggest questions"]):
        return None, ("I can search and filter the catalogue, find budget options, sort by price or rating, "
                      "recommend products, compare items, and summarize the dataset. Try: "
                      "'women's dresses under 2000', 'top 5 highest rated sneakers', "
                      "'black products from UrbanStyle', or 'recommend men's casual wear'.")
    if re.search(r"\b(hi|hello|hey)\b", q):
        return None, "Hello! I'm StyleIQ. Tell me what kind of fashion product you're looking for."

    # Intent: recommendations / general search
    for g in ["men","women","unisex"]:
        if re.search(rf"\b{g}\b", q):
            result = result[result.Gender.str.lower() == g]
            applied.append(g.title())

    # category/subcategory matching
    subcats = sorted(df.Subcategory.dropna().unique(), key=lambda x: len(str(x)), reverse=True)
    matched_sub = next((x for x in subcats if str(x).lower() in q), None)
    if matched_sub:
        result = result[result.Subcategory.str.lower() == str(matched_sub).lower()]
        applied.append(str(matched_sub))
    else:
        for cat in df.Category.dropna().unique():
            if str(cat).lower() in q:
                result = result[result.Category.str.lower() == str(cat).lower()]
                applied.append(str(cat))
                break

    for color in df.Color.dropna().unique():
        if re.search(rf"\b{re.escape(str(color).lower())}\b", q):
            result = result[result.Color.str.lower() == str(color).lower()]
            applied.append(str(color))
            break

    for brand in df.Brand.dropna().unique():
        if str(brand).lower() in q:
            result = result[result.Brand.str.lower() == str(brand).lower()]
            applied.append(str(brand))
            break

    size_match = re.search(r"\bsize\s*(xs|s|m|l|xl|xxl)\b", q)
    if size_match:
        result = result[result.Size.str.lower() == size_match.group(1)]
        applied.append("Size " + size_match.group(1).upper())

    rating_match = re.search(r"(?:rating|rated)\s*(?:above|over|greater than|>)\s*(\d(?:\.\d)?)", q)
    if rating_match:
        v = float(rating_match.group(1))
        result = result[result.Rating > v]
        applied.append(f"Rating > {v}")

    price_match = re.search(r"(?:under|below|less than|max(?:imum)?|budget)\s*(?:₹|rs\.?|inr)?\s*([\d,]+)", q)
    if price_match:
        v = int(price_match.group(1).replace(",",""))
        result = result[result.Price_INR <= v]
        applied.append("Budget ≤ " + inr(v))
    else:
        price_match = re.search(r"(?:over|above|more than|min(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*([\d,]+)", q)
        if price_match:
            v = int(price_match.group(1).replace(",",""))
            result = result[result.Price_INR >= v]
            applied.append("Price ≥ " + inr(v))

    # intent sorting
    if any(x in q for x in ["cheapest","lowest price","least expensive","budget friendly"]):
        result = result.sort_values(["Price_INR","Rating"], ascending=[True,False])
        sort_name = "lowest price"
    elif any(x in q for x in ["most expensive","costliest","highest price","premium"]):
        result = result.sort_values(["Price_INR","Rating"], ascending=[False,False])
        sort_name = "highest price"
    else:
        result = result.sort_values(["Rating","Price_INR"], ascending=[False,True])
        sort_name = "highest rating"

    top = re.search(r"\b(?:top|first)\s*(\d+)\b", q)
    limit = min(int(top.group(1)), 100) if top else 10
    total = len(result)
    if total == 0:
        return pd.DataFrame(), "I couldn't find a match. Try removing one filter or increasing your budget."
    result = result.head(limit)
    summary = f"I found **{total:,} matching products**. Showing {len(result)}; sorted by {sort_name}."
    if applied:
        summary += " Filters: " + ", ".join(applied) + "."
    return result, summary

def make_recommendations(gender, category, budget, min_rating, count):
    d = df.copy()
    if gender != "All":
        d = d[d.Gender == gender]
    if category != "All":
        d = d[d.Category == category]
    d = d[(d.Price_INR <= budget) & (d.Rating >= min_rating)]
    # value score balances rating and affordability
    if len(d):
        d = d.copy()
        d["Value_Score"] = (d.Rating / 5) * 0.7 + (1 - d.Price_INR / max(budget, 1)) * 0.3
        d = d.sort_values(["Value_Score","Rating"], ascending=False).head(count)
    return d

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🛍️ StyleIQ")
    st.caption("Fashion catalogue assistant")
    page = st.radio("Workspace", ["Chat assistant", "Product explorer", "Recommendations", "Analytics", "About"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Catalogue status**")
    st.metric("Products indexed", f"{len(df):,}")
    st.caption("Data source: supplied fashion_dataset_1000.csv")

# ---------- Header ----------
st.markdown('<div class="hero"><h1>StyleIQ Fashion Assistant</h1><p>Discover products, explore trends, compare prices and get catalogue-based recommendations.</p></div>', unsafe_allow_html=True)

if page == "Chat assistant":
    st.subheader("💬 Chat with your fashion catalogue")
    st.caption("Ask in everyday language. Results are grounded in the CSV dataset.")
    if "messages_pro" not in st.session_state:
        st.session_state.messages_pro = [{"role":"assistant","content":"Welcome to StyleIQ. What are you shopping for today? You can mention category, gender, colour, brand, rating or budget."}]
    for m in st.session_state.messages_pro:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("data") is not None:
                st.dataframe(product_table(m["data"]), use_container_width=True, hide_index=True)
    prompt = st.chat_input("Example: Find women's dresses under ₹2500...")
    if prompt:
        st.session_state.messages_pro.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        data, response = parse_chat_query(prompt)
        st.session_state.messages_pro.append({"role":"assistant","content":response,"data":data if isinstance(data,pd.DataFrame) else None})
        with st.chat_message("assistant"):
            st.markdown(response)
            if isinstance(data,pd.DataFrame) and len(data):
                st.dataframe(product_table(data), use_container_width=True, hide_index=True)
    c1,c2,c3 = st.columns(3)
    for col, textq in zip([c1,c2,c3], ["Show black dresses","Cheapest 5 sneakers","Women products under 2000"]):
        if col.button(textq, use_container_width=True):
            data, response = parse_chat_query(textq)
            st.session_state.messages_pro.append({"role":"user","content":textq})
            st.session_state.messages_pro.append({"role":"assistant","content":response,"data":data if isinstance(data,pd.DataFrame) else None})
            st.rerun()

elif page == "Product explorer":
    st.subheader("🔎 Product explorer")
    a,b,c,dcol = st.columns(4)
    with a: cats = st.multiselect("Category", sorted(df.Category.unique()))
    with b: genders = st.multiselect("Gender", sorted(df.Gender.unique()))
    with c: colors = st.multiselect("Colour", sorted(df.Color.unique()))
    with dcol: brands = st.multiselect("Brand", sorted(df.Brand.unique()))
    pmin, pmax = int(df.Price_INR.min()), int(df.Price_INR.max())
    price_range = st.slider("Price range (INR)", pmin, pmax, (pmin,pmax), step=100)
    rating = st.slider("Minimum rating", 3.0, 5.0, 3.0, 0.1)
    search = st.text_input("Search product / subcategory")
    out = df.copy()
    if cats: out = out[out.Category.isin(cats)]
    if genders: out = out[out.Gender.isin(genders)]
    if colors: out = out[out.Color.isin(colors)]
    if brands: out = out[out.Brand.isin(brands)]
    out = out[out.Price_INR.between(*price_range) & (out.Rating >= rating)]
    if search: out = out[out.Subcategory.str.contains(search, case=False, na=False)]
    st.write(f"**{len(out):,} products found**")
    st.dataframe(product_table(out), use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export filtered products CSV", out.to_csv(index=False), "filtered_fashion_products.csv", "text/csv")

elif page == "Recommendations":
    st.subheader("✨ Product recommendations")
    x,y,z,w = st.columns(4)
    with x: gender = st.selectbox("For", ["All"] + sorted(df.Gender.unique()))
    with y: category = st.selectbox("Category", ["All"] + sorted(df.Category.unique()))
    with z: budget = st.number_input("Maximum budget (₹)", min_value=100, max_value=int(df.Price_INR.max()), value=2500, step=100)
    with w: min_rating = st.slider("Minimum rating", 3.0, 5.0, 4.0, 0.1)
    count = st.slider("Number of recommendations", 3, 20, 5)
    if st.button("Generate recommendations", type="primary"):
        recs = make_recommendations(gender, category, budget, min_rating, count)
        if recs.empty:
            st.warning("No products match those preferences. Try a higher budget or lower rating.")
        else:
            st.success(f"Found {len(recs)} recommendations.")
            st.dataframe(product_table(recs), use_container_width=True, hide_index=True)
            st.download_button("Download recommendations", recs.to_csv(index=False), "fashion_recommendations.csv", "text/csv")

elif page == "Analytics":
    st.subheader("📊 Catalogue analytics")
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Total products", f"{len(df):,}")
    m2.metric("Average price", inr(df.Price_INR.mean()))
    m3.metric("Average rating", f"{df.Rating.mean():.2f} / 5")
    m4.metric("Brands", f"{df.Brand.nunique()}")
    l,r = st.columns(2)
    with l:
        fig = px.histogram(df, x="Category", color="Category", title="Products by category")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        fig = px.histogram(df, x="Price_INR", nbins=25, title="Price distribution", labels={"Price_INR":"Price (INR)"})
        st.plotly_chart(fig, use_container_width=True)
    l,r = st.columns(2)
    with l:
        avg = df.groupby("Subcategory", as_index=False).Price_INR.mean().sort_values("Price_INR", ascending=False)
        fig = px.bar(avg, x="Subcategory", y="Price_INR", title="Average price by product type")
        st.plotly_chart(fig, use_container_width=True)
    with r:
        ratings = df.groupby("Rating", as_index=False).size()
        fig = px.bar(ratings, x="Rating", y="size", title="Rating distribution")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("**Dataset preview**")
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)
    st.download_button("Download complete dataset", df.to_csv(index=False), "fashion_dataset_1000.csv", "text/csv")

elif page == "About":
    st.subheader("About StyleIQ")
    st.markdown("""
    **StyleIQ** is a catalogue-grounded fashion assistant built on the supplied 1,000-row CSV.

    **Professional features**
    - Conversational product search with filters for gender, category, subcategory, colour, brand, size, price and rating.
    - Product explorer with combined filters and CSV export.
    - Rule-based recommendations using rating and affordability.
    - Interactive catalogue analytics.
    - Dataset download and transparent local data processing.

    **Technology:** Python, Streamlit, Pandas and Plotly.

    **Important data note:** The supplied dataset is synthetic/demo data. It is useful for demonstrating data analysis and chatbot workflows, but it should not be represented as real retailer inventory or customer purchase data.
    """)
    st.info("This version works locally without an API key. Its chat understanding is rule-based, not a generative LLM. A live AI model can be connected later for more flexible conversation.")
