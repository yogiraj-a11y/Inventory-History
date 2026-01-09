import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ==========================================
# SETUP & CONFIG
# ==========================================
st.set_page_config(page_title="Inventory & Orders V2", layout="wide")

INVENTORY_FILE = "master_inventory_data.parquet"
ORDERS_FILE = "master_order_data.parquet"

# ==========================================
# DATA LOADING
# ==========================================
@st.cache_data
def load_data():
    data = {}
    try:
        data['inv'] = pd.read_parquet(INVENTORY_FILE)
    except FileNotFoundError:
        data['inv'] = None
    
    try:
        data['orders'] = pd.read_parquet(ORDERS_FILE)
    except FileNotFoundError:
        data['orders'] = None
    
    return data

data_store = load_data()
df_inv = data_store['inv']
df_ord = data_store['orders']

if df_inv is None:
    st.error(f"Missing {INVENTORY_FILE}. Please run process_data.py first.")
    st.stop()

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.header("Filters")

# Date Logic
min_date = df_inv['Date'].min()
max_date = df_inv['Date'].max()

start_date = pd.to_datetime(st.sidebar.date_input("Start Date", min_date))
end_date = pd.to_datetime(st.sidebar.date_input("End Date", max_date))

# Search Logic
unique_asins = df_inv['asin'].unique()
target_asin = st.sidebar.text_input("Enter ASIN", value="", help="Enter ASIN to see Inventory & Orders").strip()

# ==========================================
# MAIN LOGIC
# ==========================================
st.title("📦 Inventory & Order Dashboard V2")

if target_asin:
    # 1. Filter Inventory
    asin_inv = df_inv[df_inv['asin'] == target_asin]
    asin_inv_filtered = asin_inv[(asin_inv['Date'] >= start_date) & (asin_inv['Date'] <= end_date)]

    # 2. Filter Orders (if file exists)
    asin_orders = pd.DataFrame()
    if df_ord is not None:
        # Find orders linked to this ASIN
        asin_orders = df_ord[df_ord['asin'] == target_asin]
        
    if asin_inv_filtered.empty:
        st.warning(f"No Inventory data found for {target_asin} in this period.")
    else:
        # Product Info
        latest = asin_inv_filtered.iloc[-1]
        st.write(f"**Product:** {latest['product-name']} | **SKU:** {latest['sku']}")

        # Split Data by Region
        inv_uk = asin_inv_filtered[asin_inv_filtered['Region'] == 'UK']
        inv_eu = asin_inv_filtered[asin_inv_filtered['Region'] == 'EU']

        # Filter Orders by Region & Date for Visualization
        # UK Orders: Target_Region = UK
        ord_uk = asin_orders[asin_orders['Target_Region'] == 'UK'] if not asin_orders.empty else pd.DataFrame()
        
        # EU Orders: Target_Region = EU
        ord_eu = asin_orders[asin_orders['Target_Region'] == 'EU'] if not asin_orders.empty else pd.DataFrame()

        # ==========================================
        # PLOTTING FUNCTION
        # ==========================================
        def create_combo_chart(inv_data, ord_data, title, is_eu=False):
            fig = go.Figure()

            # --- A. INVENTORY LINES (Left Axis) ---
            fig.add_trace(go.Scatter(x=inv_data['Date'], y=inv_data['Fulfillable Quantity'], name='Available', line=dict(color='green'), connectgaps=True))
            fig.add_trace(go.Scatter(x=inv_data['Date'], y=inv_data['Reserved'], name='Reserved', line=dict(color='orange'), connectgaps=True))
            fig.add_trace(go.Scatter(x=inv_data['Date'], y=inv_data['Inbound'], name='Inbound', line=dict(color='blue'), connectgaps=True))

            # --- B. ORDER BARS (Overlay) ---
            if not ord_data.empty:
                # 1. Dawson Orders (Common to both)
                dawson = ord_data[ord_data['Warehouse'] == 'Dawson']
                if not dawson.empty:
                    # Placed
                    placed = dawson.groupby('Order Date')['Quantity'].sum().reset_index()
                    fig.add_trace(go.Bar(x=placed['Order Date'], y=placed['Quantity'], name='Order Placed (Dawson)', marker_color='purple', opacity=0.6))
                    
                    # Dispatched
                    dispatched = dawson.groupby('Dispatch Date')['Quantity'].sum().reset_index()
                    fig.add_trace(go.Bar(x=dispatched['Dispatch Date'], y=dispatched['Quantity'], name='Dispatched (Dawson)', marker_color='red', opacity=0.6))

                # 2. Romania Orders (EU Only)
                if is_eu:
                    romania = ord_data[ord_data['Warehouse'] == 'Romania']
                    if not romania.empty:
                        # Placed (RO)
                        r_placed = romania.groupby('Order Date')['Quantity'].sum().reset_index()
                        fig.add_trace(go.Bar(x=r_placed['Order Date'], y=r_placed['Quantity'], name='Order Placed (RO)', marker_color='#FF69B4', opacity=0.6)) # Hot Pink
                        
                        # Dispatched (RO)
                        r_disp = romania.groupby('Dispatch Date')['Quantity'].sum().reset_index()
                        fig.add_trace(go.Bar(x=r_disp['Dispatch Date'], y=r_disp['Quantity'], name='Dispatched (RO)', marker_color='#8B0000', opacity=0.6)) # Dark Red

            fig.update_layout(title=title, height=500, hovermode="x unified", barmode='group')
            return fig

        # ==========================================
        # VISUALIZATION
        # ==========================================
        
        # 1. UK PLOT
        st.subheader("🇬🇧 UK Overview")
        st.plotly_chart(create_combo_chart(inv_uk, ord_uk, "UK Inventory & Orders"), use_container_width=True)

        # 2. EU PLOT
        st.subheader("🇪🇺 EU Overview")
        st.plotly_chart(create_combo_chart(inv_eu, ord_eu, "EU Inventory & Orders (Dawson + Romania)", is_eu=True), use_container_width=True)

        st.divider()

        # ==========================================
        # ORDER TABLES
        # ==========================================
        st.subheader("📋 Order History Details")
        
        col1, col2 = st.columns(2)
        
        # Column Helper
        display_cols = ['Order Date', 'Dispatch Date', 'Quantity', 'Order ID', 'Warehouse', 'Channel Name', 'sku']

        with col1:
            st.write("**UK Orders**")
            if not ord_uk.empty:
                # Filter by selected date range for the table
                tbl_uk = ord_uk[(ord_uk['Order Date'] >= start_date) & (ord_uk['Order Date'] <= end_date)]
                st.dataframe(tbl_uk[display_cols].sort_values('Order Date', ascending=False), hide_index=True)
            else:
                st.info("No UK Orders found.")

        with col2:
            st.write("**EU Orders**")
            if not ord_eu.empty:
                tbl_eu = ord_eu[(ord_eu['Order Date'] >= start_date) & (ord_eu['Order Date'] <= end_date)]
                st.dataframe(tbl_eu[display_cols].sort_values('Order Date', ascending=False), hide_index=True)
            else:
                st.info("No EU Orders found.")

else:

    st.info("👈 Please enter an ASIN in the sidebar.")

