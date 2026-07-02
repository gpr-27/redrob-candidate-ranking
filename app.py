import streamlit as st
import json
import pandas as pd
import io
from rank import compute_composite_score
from scoring.reasoning_generator import generate_reasoning

st.set_page_config(
    page_title="Redrob Candidate Discovery & Ranking Sandbox",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        color: #1F2729;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #E9ECEF;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    </style>
""", unsafe_allow_index=True)

st.markdown('<div class="main-title">🔍 Redrob Candidate Discovery & Ranking Sandbox</div>', unsafe_allow_index=True)
st.markdown('<div class="subtitle">Deterministic, rule-based ranking engine for Senior AI/ML Engineer role</div>', unsafe_allow_index=True)

# Sidebar
st.sidebar.header("Settings & Input")

# File uploader
uploaded_file = st.sidebar.file_uploader(
    "Upload Candidates JSONL/JSON",
    type=["jsonl", "json"],
    help="Upload a custom candidates file to rank. If none is uploaded, the pre-loaded 50-candidate sample will be used."
)

# Load candidates
candidates = []
source_name = ""

if uploaded_file is not None:
    try:
        content = uploaded_file.getvalue().decode("utf-8")
        if uploaded_file.name.endswith(".jsonl"):
            for line in content.splitlines():
                if line.strip():
                    candidates.append(json.loads(line))
            source_name = f"Uploaded JSONL ({len(candidates)} candidates)"
        else:
            candidates = json.loads(content)
            source_name = f"Uploaded JSON ({len(candidates)} candidates)"
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")

if not candidates:
    try:
        with open("sample_candidates.json", "r", encoding="utf-8") as f:
            candidates = json.load(f)
        source_name = f"Default Sample Candidates ({len(candidates)} candidates)"
    except Exception as e:
        st.error(f"Could not load default sample candidates: {e}")

st.sidebar.info(f"**Active Source:**\n{source_name}")

# Run ranking
if candidates:
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 Run Ranker", type="primary"):
        with st.spinner("Processing and ranking candidates..."):
            scored_list = []
            honeypots_count = 0
            
            for c in candidates:
                score, breakdown = compute_composite_score(c)
                if breakdown.get('honeypot', 1.0) < 0.5:
                    honeypots_count += 1
                scored_list.append((score, c['candidate_id'], breakdown, c))
            
            # Sort by score descending, then candidate_id ascending
            scored_list.sort(key=lambda x: (-x[0], x[1]))
            
            # Round scores and re-sort to handle rounded ties deterministically
            top_results = []
            for score, cand_id, breakdown, c in scored_list:
                score_rounded = round(score, 4)
                top_results.append((score_rounded, cand_id, breakdown, c))
            top_results.sort(key=lambda x: (-x[0], x[1]))
            
            # Build DataFrame for display
            rows = []
            for rank_idx, (score_rounded, cand_id, breakdown, c) in enumerate(top_results):
                rank = rank_idx + 1
                reasoning = generate_reasoning(c, rank, breakdown)
                p = c['profile']
                rows.append({
                    "Rank": rank,
                    "Candidate ID": cand_id,
                    "Score": score_rounded,
                    "Name": p.get("anonymized_name", "Anonymized"),
                    "Current Title": p.get("current_title", "N/A"),
                    "Company": p.get("current_company", "N/A"),
                    "YoE": p.get("years_of_experience", 0.0),
                    "Location": f"{p.get('location', 'N/A')}, {p.get('country', 'N/A')}",
                    "Reasoning": reasoning,
                    # Breakdown details for expander
                    "Title Fit": round(breakdown.get('title', 0), 3),
                    "Career Quality": round(breakdown.get('career', 0), 3),
                    "Skills Match": round(breakdown.get('skills', 0), 3),
                    "Behavioral": round(breakdown.get('behavioral', 0), 3),
                    "Experience Fit": round(breakdown.get('experience', 0), 3),
                    "Honeypot Mult": round(breakdown.get('honeypot', 1.0), 3)
                })
            
            df = pd.DataFrame(rows)
            
            # Store in session state
            st.session_state['ranked_df'] = df
            st.session_state['honeypots_detected'] = honeypots_count
            st.session_state['total_processed'] = len(candidates)
            st.success("Ranking completed successfully!")

# Display results if available
if 'ranked_df' in st.session_state:
    df = st.session_state['ranked_df']
    total = st.session_state['total_processed']
    h_count = st.session_state['honeypots_detected']
    
    # Metrics row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.9rem; color: #666;">TOTAL CANDIDATES PROCESSED</div>
                <div style="font-size: 2rem; font-weight: bold; color: #1F2729;">{total:,}</div>
            </div>
        """, unsafe_allow_index=True)
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.9rem; color: #666;">HONEYPOTS DETECTED & FILTERED</div>
                <div style="font-size: 2rem; font-weight: bold; color: #D9534F;">{h_count}</div>
            </div>
        """, unsafe_allow_index=True)
    with col3:
        # Download buttons
        st.markdown('<div class="metric-card" style="padding-bottom: 1.15rem;">', unsafe_allow_index=True)
        st.write("**DOWNLOAD RESULTS**")
        
        # CSV download
        csv_buffer = io.StringIO()
        df_csv = df[["Candidate ID", "Rank", "Score", "Reasoning"]].rename(columns={
            "Candidate ID": "candidate_id",
            "Rank": "rank",
            "Score": "score",
            "Reasoning": "reasoning"
        })
        df_csv["score"] = df_csv["score"].map(lambda x: f"{x:.4f}")
        df_csv.to_csv(csv_buffer, index=False)
        
        st.download_button(
            label="📥 Download submission.csv",
            data=csv_buffer.getvalue(),
            file_name="submission.csv",
            mime="text/csv"
        )
        st.markdown('</div>', unsafe_allow_index=True)

    st.markdown("---")
    
    # Results Table
    st.subheader("Ranked Candidates (Top 100 or All)")
    
    # Let user select a candidate to see their full profile and breakdown
    st.markdown("### Interactive Candidate Explorer")
    selected_cand_id = st.selectbox(
        "Select a candidate to view their detailed score breakdown and profile:",
        options=df["Candidate ID"].tolist()
    )
    
    if selected_cand_id:
        cand_row = df[df["Candidate ID"] == selected_cand_id].iloc[0]
        
        # Find original candidate object
        orig_cand = next((c for c in candidates if c['candidate_id'] == selected_cand_id), None)
        
        if orig_cand:
            col_left, col_right = st.columns([1, 2])
            
            with col_left:
                st.markdown("#### Score Breakdown")
                breakdown_df = pd.DataFrame([
                    {"Component": "Title Fit (25%)", "Score": cand_row["Title Fit"]},
                    {"Component": "Career Quality (25%)", "Score": cand_row["Career Quality"]},
                    {"Component": "Skills Match (20%)", "Score": cand_row["Skills Match"]},
                    {"Component": "Behavioral Signals (15%)", "Score": cand_row["Behavioral"]},
                    {"Component": "Experience Fit (8%)", "Score": cand_row["Experience Fit"]},
                    {"Component": "Honeypot Multiplier", "Score": cand_row["Honeypot Mult"]}
                ])
                st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
                st.metric("Final Composite Score", f"{cand_row['Score']:.4f}")
                
            with col_right:
                st.markdown(f"#### Profile: {cand_row['Name']} ({selected_cand_id})")
                st.markdown(f"**Headline:** {orig_cand['profile'].get('headline', 'N/A')}")
                st.markdown(f"**Summary:** {orig_cand['profile'].get('summary', 'N/A')}")
                
                # Skills
                skills_list = [f"{s['name']} ({s['proficiency']}, {s.get('duration_months', 0)}mo)" for s in orig_cand.get('skills', [])]
                st.markdown(f"**Skills:** {', '.join(skills_list)}")
                
                # Career History
                st.markdown("**Career History:**")
                for ch in orig_cand.get('career_history', []):
                    end_date = ch.get('end_date') or "Present"
                    st.markdown(f"- **{ch.get('title')}** at *{ch.get('company')}* ({ch.get('start_date')} to {end_date}, {ch.get('duration_months')} months)")
                    st.markdown(f"  *Description:* {ch.get('description')}")
                    
                # Education
                st.markdown("**Education:**")
                for edu in orig_cand.get('education', []):
                    st.markdown(f"- **{edu.get('degree')} in {edu.get('field_of_study')}** from *{edu.get('institution')}* (Tier: {edu.get('tier', 'N/A')})")

    st.markdown("---")
    st.markdown("### Full Ranked List")
    st.dataframe(
        df[["Rank", "Candidate ID", "Score", "Name", "Current Title", "Company", "YoE", "Location", "Reasoning"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Click the **🚀 Run Ranker** button in the sidebar to process and rank the candidates.")
