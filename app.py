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
    
    /* Sidebar text color */
    [data-testid="stSidebar"] .stText, 
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .st-ae, [data-testid="stSidebar"] .stMarkdown { 
        color: white !important; 
    }

    /* Header Metrics Card Styling */
    .metric-container {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border-left: 6px solid #facc15;
        min-height: 100px;
        margin-bottom: 10px;
    }
    .metric-label { font-size: 12px; color: #4b5563; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 18px; font-weight: 800; color: #000000; line-height: 1.2; }
    
    /* Status Headers */
    .critical-header { color: #ff4b4b; font-size: 24px; font-weight: bold; margin-top: 20px; }
    .improve-header { color: #facc15; font-size: 24px; font-weight: bold; margin-top: 20px; }
    
    /* Table Row Hover Effect */
    table tbody tr:hover {
        background-color: #ffd700 !important;
        color: #000000 !important;
        transition: background-color 0.2s ease, color 0.2s ease;
    }
    table tbody tr {
        transition: background-color 0.2s ease, color 0.2s ease;
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
    return st.session_state["password_correct"]

# --- DATA PROCESSING ENGINE ---
@st.cache_data(ttl=600)
def load_and_transform_data(file_path):
    try:
        raw_df = pd.read_csv(file_path, keep_default_na=False)
        month_keywords = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_cols = [col for col in raw_df.columns if any(m in col for m in month_keywords)]
        
        id_vars = ['KPI', 'Unit', 'Platform', 'Target', 'Threshold', 'Source']
        df_long = pd.melt(raw_df, id_vars=id_vars, value_vars=month_cols, var_name='month_str', value_name='raw_val')
        
        def process_value(val):
            val_str = str(val).strip()
            if val_str.upper() == "NA": return None
            if val_str in ["", "-", " "]: return "FILL_MEDIAN"
            try: return float(val_str.replace('%', '').replace(',', '').strip())
            except ValueError: return None

        df_long['kpi_value'] = df_long['raw_val'].apply(process_value)
        
        # Numeric conversion for logic
        df_long['Target_num'] = pd.to_numeric(df_long['Target'].astype(str).str.replace('%',''), errors='coerce')
        df_long['Threshold_num'] = pd.to_numeric(df_long['Threshold'].astype(str).str.replace('%',''), errors='coerce')
        
        # Median Imputation
        temp_numeric = pd.to_numeric(df_long['kpi_value'], errors='coerce')
        medians = temp_numeric.groupby([df_long['KPI'], df_long['Platform']]).transform('median')
        df_long['kpi_value'] = np.where(df_long['kpi_value'] == "FILL_MEDIAN", medians, df_long['kpi_value'])
        df_long['kpi_value'] = pd.to_numeric(df_long['kpi_value'], errors='coerce')
        df_long['month'] = pd.to_datetime(df_long['month_str'], format='mixed', errors='coerce')
        
        return df_long.sort_values(by=['KPI', 'month'])
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# --- MAIN UI ---
def main():
    if check_password():
        df = load_and_transform_data('data/input/app_kpi.csv')
        if df.empty: return

        st.sidebar.title("📖 Book of KPIs")
        menu_choice = st.sidebar.radio("Navigation", ["Summary", "KPI Explorer", "KPI Trends"])

        if menu_choice == "Summary":
            st.title("📊 Dashboard Health Summary")
            
            # Find latest month data for each KPI/Platform
            latest_data = df.dropna(subset=['kpi_value']).sort_values('month').groupby(['KPI', 'Platform']).last().reset_index()
            
            critical_rows = []
            improve_rows = []

            for _, row in latest_data.iterrows():
                val = row['kpi_value']
                tgt = row['Target_num']
                thr = row['Threshold_num']
                unit = row['Unit']
                
                # Logic: Is it a 'Higher is Better' or 'Lower is Better' metric?
                is_critical = False
                is_improvement = False
                
                if tgt > thr: # Higher is better (e.g. 99% Crash Free)
                    if val < thr: is_critical = True
                    elif val < tgt: is_improvement = True
                else: # Lower is better (e.g. 100 RAI)
                    if val > thr: is_critical = True
                    elif val > tgt: is_improvement = True

                row_dict = {
                    "KPI Name": row['KPI'],
                    "Platform": row['Platform'],
                    "Current Value": f"{val} {unit}",
                    "Reference": "" 
                }

                if is_critical:
                    row_dict["Threshold"] = f"{row['Threshold']} {unit}"
                    critical_rows.append(row_dict)
                elif is_improvement:
                    row_dict["Target"] = f"{row['Target']} {unit}"
                    improve_rows.append(row_dict)

            # --- RENDER TABLES ---
            st.markdown('<div class="critical-header">🚨 Critical Attention - Fix Required</div>', unsafe_allow_html=True)
            if critical_rows:
                st.table(pd.DataFrame(critical_rows)[["KPI Name", "Platform", "Current Value", "Threshold"]])
            else:
                st.success("No critical items found.")

            st.markdown('<div class="improve-header">⚠️ Needs Improvement</div>', unsafe_allow_html=True)
            if improve_rows:
                st.table(pd.DataFrame(improve_rows)[["KPI Name", "Platform", "Current Value", "Target"]])
            else:
                st.success("All targets met!")

        elif menu_choice == "KPI Explorer":
            all_kpis = sorted([k for k in df['KPI'].dropna().unique() if str(k).strip() != ""])
            search = st.sidebar.text_input("🔍 Search KPI", "")
            filtered_kpis = [k for k in all_kpis if search.lower() in k.lower()]
            selected_kpi = st.sidebar.radio("Select KPI:", filtered_kpis, label_visibility="collapsed")

            if selected_kpi:
                kpi_data = df[df['KPI'] == selected_kpi]
                unit = kpi_data['Unit'].iloc[0]
                
                # Header with column D+B and E+B display
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.markdown(f'<div class="metric-container"><div class="metric-label">KPI Name</div><div class="metric-value">{selected_kpi}</div></div>', unsafe_allow_html=True)
                with c2: st.markdown(f'<div class="metric-container"><div class="metric-label">Target (D+B)</div><div class="metric-value">{kpi_data["Target"].iloc[0]} {unit}</div></div>', unsafe_allow_html=True)
                with c3: st.markdown(f'<div class="metric-container"><div class="metric-label">Threshold (E+B)</div><div class="metric-value">{kpi_data["Threshold"].iloc[0]} {unit}</div></div>', unsafe_allow_html=True)
                with c4: st.markdown(f'<div class="metric-container"><div class="metric-label">Data Source</div><div class="metric-value">{kpi_data["Source"].iloc[0]}</div></div>', unsafe_allow_html=True)

                st.markdown("---")

                fig = px.line(kpi_data, x='month', y='kpi_value', color='Platform', markers=True, 
                              title=f"Trend: {selected_kpi} ({unit})", template="plotly_dark")
                fig.update_layout(hovermode="x unified", xaxis=dict(hoverformat="%b, %Y", tickformat="%b, %Y", title=""))
                fig.update_traces(hovertemplate="<b>%{fullData.name}</b>: %{y}<extra></extra>")
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("📊 View Data Table", expanded=True):
                    order_helper = kpi_data[['month_str', 'month']].drop_duplicates().sort_values('month')
                    pivot_view = kpi_data.pivot(index='Platform', columns='month_str', values='kpi_value')
                    st.dataframe(pivot_view.reindex(columns=order_helper['month_str'].tolist()), use_container_width=True)

        elif menu_choice == "KPI Trends":
            st.title("📈 KPI Performance Trends")
            
            # Get the last two months for comparison
            valid_data = df.dropna(subset=['kpi_value']).sort_values('month')
            unique_months = valid_data['month'].unique()
            
            if len(unique_months) < 2:
                st.warning("Not enough data for trend analysis")
                return
            
            latest_month = unique_months[-1]
            prev_month = unique_months[-2]
            
            # Get data for latest and previous month
            latest_data = valid_data[valid_data['month'] == latest_month].groupby(['KPI', 'Platform']).last().reset_index()
            prev_data = valid_data[valid_data['month'] == prev_month].groupby(['KPI', 'Platform']).last().reset_index()
            prev_data = prev_data[['KPI', 'Platform', 'kpi_value']].rename(columns={'kpi_value': 'prev_value'})
            
            # Merge to compare
            comparison = latest_data.merge(prev_data, on=['KPI', 'Platform'], how='left')
            
            # Determine improvement
            def is_improved(row):
                if pd.isna(row['prev_value']):
                    return None
                val = row['kpi_value']
                prev_val = row['prev_value']
                tgt = row['Target_num']
                thr = row['Threshold_num']
                
                if tgt > thr:  # Higher is better
                    return val > prev_val
                else:  # Lower is better
                    return val < prev_val
            
            comparison['Improved'] = comparison.apply(is_improved, axis=1)
            
            # Separate improved and deteriorated
            improved_rows = []
            deteriorated_rows = []
            
            for _, row in comparison.iterrows():
                if pd.isna(row['prev_value']):
                    continue
                
                unit = row['Unit']
                prev_val = row['prev_value']
                curr_val = row['kpi_value']
                change = curr_val - prev_val
                
                # Skip rows with no change
                if change == 0:
                    continue
                
                row_dict = {
                    "KPI Name": row['KPI'],
                    "Platform": row['Platform'],
                    f"Previous ({prev_month.strftime('%b %y')})": f"{prev_val:.2f} {unit}",
                    f"Latest ({latest_month.strftime('%b %y')})": f"{curr_val:.2f} {unit}",
                    "Change": f"{change:+.2f} {unit}"
                }
                
                if row['Improved']:
                    improved_rows.append(row_dict)
                else:
                    deteriorated_rows.append(row_dict)
            
            # --- RENDER TABLES ---
            st.markdown('<div class="improve-header">✅ Improved KPIs</div>', unsafe_allow_html=True)
            if improved_rows:
                st.table(pd.DataFrame(improved_rows))
            else:
                st.info("No improvements this period")

            st.markdown('<div class="critical-header">📉 Deteriorated KPIs</div>', unsafe_allow_html=True)
            if deteriorated_rows:
                st.table(pd.DataFrame(deteriorated_rows))
            else:
                st.success("No deterioration this period!")

if __name__ == "__main__":
    main()