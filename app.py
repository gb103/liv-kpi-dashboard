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
    
    /* Force sidebar text to white */
    [data-testid="stSidebar"] .stText, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .st-ae,
    [data-testid="stSidebar"] .stMarkdown { 
        color: white !important; 
    }

    /* Custom Metric Styling: Black text on white containers */
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

# --- 2. DATA PROCESSING ENGINE ---
@st.cache_data(ttl=600)
def load_and_transform_data(file_path):
    try:
        raw_df = pd.read_csv(file_path, keep_default_na=False)
        
        # Identify month columns based on your sheet
        month_keywords = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_cols = [col for col in raw_df.columns if any(m in col for m in month_keywords)]
        
        id_vars = ['KPI', 'Unit', 'Platform', 'Target', 'Source']
        df_long = pd.melt(raw_df, id_vars=id_vars, value_vars=month_cols, 
                          var_name='month_str', value_name='raw_val')
        
        def process_value(val):
            val_str = str(val).strip()
            # "Wherever NA is mentioned... let's not draw anything"
            if val_str.upper() == "NA": return None
            # "If any value is blank, then just fill that with median"
            if val_str in ["", "-", " "]: return "FILL_MEDIAN"
            try:
                return float(val_str.replace('%', '').replace(',', '').strip())
            except ValueError:
                return None

        df_long['temp_val'] = df_long['raw_val'].apply(process_value)
        df_long['kpi_value'] = pd.to_numeric(df_long['temp_val'], errors='coerce')
        
        # Median Imputation
        medians = df_long.groupby(['KPI', 'Platform'])['kpi_value'].transform('median')
        df_long.loc[df_long['temp_val'] == "FILL_MEDIAN", 'kpi_value'] = medians
        
        # Convert to datetime (defaults to 1st of month, handled in hover formatting)
        df_long['month'] = pd.to_datetime(df_long['month_str'], format='%b, %Y', errors='coerce')
        return df_long.sort_values(by=['KPI', 'month'])
    
    except Exception as e:
        st.error(f"Error processing data: {e}")
        return pd.DataFrame()

# --- 3. UI LAYOUT ---
def main():
    st.sidebar.title("📖 Book of KPIs")
    
    df = load_and_transform_data('data/input/app_kpi.csv')

    if df.empty:
        st.error("Data could not be loaded. Please check app_kpi.csv.")
        return

    # Sidebar: Filter out blanks to fix top of list
    all_kpis = sorted([k for k in df['KPI'].dropna().unique() if str(k).strip() != ""])
    search = st.sidebar.text_input("🔍 Search KPI", "")
    filtered_kpis = [k for k in all_kpis if search.lower() in k.lower()]
    
    selected_kpi = st.sidebar.radio("Select KPI:", filtered_kpis, label_visibility="collapsed")

    if selected_kpi:
        kpi_data = df[df['KPI'] == selected_kpi]
        unit = kpi_data['Unit'].iloc[0] if 'Unit' in kpi_data.columns else ""
        target = kpi_data['Target'].iloc[0] if 'Target' in kpi_data.columns else "N/A"
        source = kpi_data['Source'].iloc[0] if not kpi_data['Source'].empty else "N/A"
        
        # Header Row
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">KPI Name</div><div class="metric-value">{selected_kpi}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">Target</div><div class="metric-value">{target} {unit}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-container"><div class="metric-label">Data Source</div><div class="metric-value">{source}</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        # Line Chart
        fig = px.line(
            kpi_data,
            x='month',
            y='kpi_value',
            color='Platform',
            markers=True,
            title=f"Platform-wise Trend: {selected_kpi} ({unit})",
            template="plotly_dark",
            labels={'kpi_value': f'Value ({unit})', 'month': ''} # Remove 'Month' label
        )

        # FIX A: Hover Formatting
        fig.update_layout(
            hovermode="x unified",
            xaxis=dict(
                hoverformat="%b, %Y", # Shows 'Dec, 2025' in unified header
                tickformat="%b, %Y",
                title="" # Remove axis title for cleaner look
            )
        )
        
        # Remove redundant 'Month' field from individual lines
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b>: %{y}<extra></extra>"
        )

        # FIX B: Y-Axis Scaling for Crash Free Rate
        if "Crash Free Rate" in selected_kpi:
            # "scale between 90 - 100 with gap of 1 for crashes"
            fig.update_yaxes(range=[90, 100], dtick=1)
        else:
            fig.update_yaxes(autorange=True)

        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

        # View Data Table - Expanded by default
        with st.expander("📊 View Data Table", expanded=True):
            pivot_view = kpi_data.pivot(index='Platform', columns='month_str', values='kpi_value')
            st.dataframe(pivot_view, use_container_width=True)

if __name__ == "__main__":
    main()