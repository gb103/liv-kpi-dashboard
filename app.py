import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Book of KPIs", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; }
    
    /* Sidebar text color for contrast */
    [data-testid="stSidebar"] .stText, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .st-ae,
    [data-testid="stSidebar"] .stMarkdown { 
        color: white !important; 
    }

    /* Header Metrics: Black text on white background cards */
    .metric-container {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border-left: 6px solid #facc15;
        min-height: 100px;
        margin-bottom: 10px;
    }
    .metric-label {
        font-size: 13px;
        color: #4b5563;
        margin-bottom: 5px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 19px;
        font-weight: 800;
        color: #000000;
        line-height: 1.2;
        word-wrap: break-word;
    }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "liv_kpi_2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# --- DATA PROCESSING ENGINE ---
@st.cache_data(ttl=600)
def load_and_transform_data(file_path):
    try:
        raw_df = pd.read_csv(file_path, keep_default_na=False)
        
        # Identify month columns
        month_keywords = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_cols = [col for col in raw_df.columns if any(m in col for m in month_keywords)]
        
        id_vars = ['KPI', 'Unit', 'Platform', 'Target', 'Source']
        df_long = pd.melt(raw_df, id_vars=id_vars, value_vars=month_cols, 
                          var_name='month_str', value_name='raw_val')
        
        def process_value(val):
            val_str = str(val).strip()
            if val_str.upper() == "NA": return None
            if val_str in ["", "-", " "]: return "FILL_MEDIAN"
            try:
                return float(val_str.replace('%', '').replace(',', '').strip())
            except ValueError:
                return None

        df_long['temp_val'] = df_long['raw_val'].apply(process_value)
        df_long['kpi_value'] = pd.to_numeric(df_long['temp_val'], errors='coerce')
        
        # Median Imputation for missing values
        medians = df_long.groupby(['KPI', 'Platform'])['kpi_value'].transform('median')
        df_long.loc[df_long['temp_val'] == "FILL_MEDIAN", 'kpi_value'] = medians
        
        # Standardize date parsing
        df_long['month'] = pd.to_datetime(df_long['month_str'], format='mixed', errors='coerce')
        
        return df_long.sort_values(by=['KPI', 'month'])
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# --- MAIN DASHBOARD ---
def main():
    if check_password():
        st.sidebar.title("📖 Book of KPIs")
        df = load_and_transform_data('data/input/app_kpi.csv')

        if df.empty:
            st.error("Data could not be loaded. Please ensure app_kpi.csv is present.")
            return

        # Sidebar navigation - filter out empty KPI rows
        all_kpis = sorted([k for k in df['KPI'].dropna().unique() if str(k).strip() != ""])
        search = st.sidebar.text_input("🔍 Search KPI", "")
        filtered_kpis = [k for k in all_kpis if search.lower() in k.lower()]
        selected_kpi = st.sidebar.radio("Select KPI:", filtered_kpis, label_visibility="collapsed")

        if selected_kpi:
            kpi_data = df[df['KPI'] == selected_kpi]
            unit = kpi_data['Unit'].iloc[0] if 'Unit' in kpi_data.columns else ""
            target = kpi_data['Target'].iloc[0] if 'Target' in kpi_data.columns else "N/A"
            source = kpi_data['Source'].iloc[0] if not kpi_data['Source'].empty else "N/A"
            
            # Header Row Metrics
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f'<div class="metric-container"><div class="metric-label">KPI Name</div><div class="metric-value">{selected_kpi}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-container"><div class="metric-label">Target</div><div class="metric-value">{target} {unit}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-container"><div class="metric-label">Data Source</div><div class="metric-value">{source}</div></div>', unsafe_allow_html=True)

            st.markdown("---")

            # LINE CHART
            fig = px.line(
                kpi_data, x='month', y='kpi_value', color='Platform', markers=True,
                title=f"Platform-wise Trend: {selected_kpi} ({unit})",
                template="plotly_dark", labels={'kpi_value': f'Value ({unit})', 'month': ''}
            )

            # Reverted to Older Code Logic: Generic Autorange for all metrics
            fig.update_yaxes(autorange=True)

            # Unified Hover Configuration
            fig.update_layout(
                hovermode="x unified",
                xaxis=dict(hoverformat="%b, %Y", tickformat="%b, %Y", title="Timeline"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig.update_traces(hovertemplate="<b>%{fullData.name}</b>: %{y}<extra></extra>")

            st.plotly_chart(fig, use_container_width=True)

            # DATA TABLE: Chronological Order
            with st.expander("📊 View Data Table", expanded=True):
                # Ensure columns follow the calendar by sorting against the actual 'month' datetime
                order_helper = kpi_data[['month_str', 'month']].drop_duplicates().sort_values('month')
                chronological_months = order_helper['month_str'].tolist()
                
                pivot_view = kpi_data.pivot(index='Platform', columns='month_str', values='kpi_value')
                # Explicitly reindex to fix sorting issues
                pivot_view = pivot_view.reindex(columns=chronological_months)
                
                st.dataframe(pivot_view, use_container_width=True)

if __name__ == "__main__":
    main()