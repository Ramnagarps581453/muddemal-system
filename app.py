import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO
from PIL import Image
import socket
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- AUTO IP DETECTOR (For local testing before cloud deployment) ---
def get_auto_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

# --- INITIALIZE SESSION STATE ---
if 'pending_items' not in st.session_state:
    st.session_state.pending_items = []

# --- GOOGLE SHEETS SETUP (Supports Local & Cloud) ---
@st.cache_resource
def init_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # 1. Try to use the local file (if you are testing on your computer)
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    except Exception:
        # 2. Use Streamlit Secrets (when deployed to the cloud)
        creds_dict = json.loads(st.secrets["google_secret"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
    client = gspread.authorize(creds)
    sheet = client.open("Muddemal_Database")
    return sheet.worksheet("Boxes"), sheet.worksheet("Items")

boxes_sheet, items_sheet = init_gsheets()

# --- HELPER FUNCTIONS ---
def get_row_by_item_id(sheet, item_id):
    col_values = sheet.col_values(1) # Column 1 is Item ID
    try:
        return col_values.index(str(item_id)) + 1
    except ValueError:
        return None

def get_next_item_id(sheet):
    col_values = sheet.col_values(1)
    if len(col_values) <= 1:
        return 1
    else:
        ids = [int(x) for x in col_values[1:] if x.isdigit()]
        return max(ids) + 1 if ids else 1

# --- STREAMLIT INTERFACE CONFIG ---
st.set_page_config(page_title="Ramanagar PS Muddemal System", layout="wide")

# Fetch all data into Pandas for fast searching and cross-referencing
with st.spinner("Syncing with Google Database..."):
    b_data = boxes_sheet.get_all_records()
    i_data = items_sheet.get_all_records()
    boxes_df = pd.DataFrame(b_data) if b_data else pd.DataFrame(columns=["Box ID", "Description"])
    items_df = pd.DataFrame(i_data) if i_data else pd.DataFrame(columns=["Item ID", "Box ID", "FIR Number", "FIR Year", "Section of Law", "PF Number", "PF Year", "Type of Article", "Status"])
    available_boxes = boxes_df["Box ID"].tolist() if not boxes_df.empty else []

# --- PROCESS QUERY PARAMETERS FOR DEEP LINKING ---
query_params = st.query_params
scanned_box = query_params.get("box_id", None)
scanned_item = query_params.get("item_id", None)

# =====================================================================
# SPECIAL WORKFLOW: DETAILED PROPERTY DETAILS PAGE (QR SCAN LINK)
# =====================================================================
if scanned_item:
    try:
        target_item_id = int(scanned_item)
    except ValueError:
        target_item_id = None

    item_row = items_df[items_df["Item ID"] == target_item_id] if target_item_id is not None else pd.DataFrame()

    if not item_row.empty:
        item = item_row.iloc[0]
        
        # Action Bar back to system
        st.markdown(
            """
            <style>
            @media print {
                .no-print { display: none !important; }
                .print-card { border: none !important; box-shadow: none !important; }
            }
            .print-card {
                background-color: #ffffff;
                padding: 25px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                margin-top: 15px;
            }
            .status-badge {
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
                display: inline-block;
            }
            </style>
            """, unsafe_style=True
        )
        
        st.sidebar.markdown("### 🔍 Quick Actions")
        if st.sidebar.button("🔙 Open Main Application"):
            st.query_params.clear()
            st.rerun()
            
        if st.sidebar.button("🖨️ Print Sheet"):
            st.markdown("<script>window.print();</script>", unsafe_style=True)

        st.subheader("📋 Ramanagar Police Station — Property Tracking Sheet")
        st.markdown(f"**Item Reference Unique ID:** `MUD-ITEM-{item['Item ID']}`")
        st.markdown("---")

        # Layout Main Summary Page Card
        st.markdown(
            f"""
            <div class="print-card">
                <table style="width:100%; border-collapse: collapse; font-family: sans-serif;">
                    <tr style="background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                        <td style="padding: 12px; font-weight: bold; width: 25%;">Property Attribute</td>
                        <td style="padding: 12px; font-weight: bold;">Registered Database Record Value</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Item ID No.</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; color: #007bff; font-weight: bold;">{item['Item ID']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Current Storage Box ID</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold; color: #e83e8c;">{item['Box ID']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Crime / FIR Number</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">{item['FIR Number']} / {item['FIR Year']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Section of Law</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-style: italic;">{item['Section of Law']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Property Form (PF) No.</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">{item['PF Number']} / {item['PF Year']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Property Description</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-size: 16px; color: #333;">{item['Type of Article']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; font-weight: bold;">Muddemal Room Status</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <span class="status-badge" style="background-color: #d4edda; color: #155724;">🔑 {item['Status']}</span>
                        </td>
                    </tr>
                </table>
            </div>
            """, unsafe_style=True
        )

        st.markdown("<br>", unsafe_style=True)
        st.markdown("### 📑 Instant Case Chain of Custody Summary Updates")
        
        # Fast Edit Panel directly inside detail view
        new_status_direct = st.selectbox("Fast Status Update:", ["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"], index=["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"].index(item['Status']) if item['Status'] in ["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"] else 0, key="direct_edit_status")
        
        if st.button("Save Live Status Change", type="primary"):
            with st.spinner("Writing update entry to master cloud ledger..."):
                row_idx = get_row_by_item_id(items_sheet, item['Item ID'])
                items_sheet.update_cell(row_idx, 9, new_status_direct)
            st.success("Ledger Entry updated seamlessly!")
            st.rerun()
            
    else:
        st.error(f"Property record with Item ID '{scanned_item}' was not discovered inside the digital system.")
        if st.button("Return to Dashboard"):
            st.query_params.clear()
            st.rerun()

# =====================================================================
# STANDARD WORKFLOW INTERFACE
# =====================================================================
else:
    st.title("🚓 Ramanagar Police Station Muddemal Room")
    st.markdown("*(Connected to Secure Google Cloud)*")
    st.markdown("---")

    menu = ["View & Update Box", "Register Properties", "Move Property", "Edit / Delete Records", "Generate QR Codes"]
    choice = st.sidebar.selectbox("Navigation Menu", menu, index=0 if scanned_box else 0)

    # =====================================================================
    # WORKFLOW 1: VIEW & UPDATE ITEMS
    # =====================================================================
    if choice == "View & Update Box" or scanned_box:
        st.subheader("📦 Box Inventory Details")
        
        if scanned_box and scanned_box in available_boxes:
            box_id = st.selectbox("Selected Box", available_boxes, index=available_boxes.index(scanned_box))
        elif available_boxes:
            box_id = st.selectbox("Select Box ID to View", available_boxes)
        else:
            st.warning("No boxes registered yet.")
            box_id = None

        if box_id:
            box_items = items_df[items_df["Box ID"] == box_id]
            
            if not box_items.empty:
                st.write(f"### Properties currently inside **{box_id}**:")
                
                display_df = box_items.copy()
                display_df["CR Number"] = display_df["FIR Number"].astype(str) + "/" + display_df["FIR Year"].astype(str)
                display_df["PF Number"] = display_df["PF Number"].astype(str) + "/" + display_df["PF Year"].astype(str)
                
                # Create a clean details link column for interactive tracking inside the data table
                display_df = display_df[["Item ID", "CR Number", "Section of Law", "PF Number", "Type of Article", "Status"]]
                st.dataframe(display_df.set_index('Item ID'), use_container_width=True)
                
                st.markdown("### 🔄 Dispatch to Court / Update Status")
                selected_item_id = st.selectbox("Select Item ID to update", box_items['Item ID'].tolist())
                new_status = st.selectbox("Change Status to", ["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"])
                
                col_btn1, col_btn2 = st.columns([2, 5])
                with col_btn1:
                    if st.button("Update Status"):
                        with st.spinner("Updating Google Database..."):
                            row_idx = get_row_by_item_id(items_sheet, selected_item_id)
                            items_sheet.update_cell(row_idx, 9, new_status) # Column 9 is Status
                        st.success(f"Status updated successfully! Refreshing...")
                        st.rerun()
                with col_btn2:
                    if st.button("👁️ Open Detailed Property Page"):
                        st.query_params.update(item_id=str(selected_item_id))
                        st.rerun()
            else:
                st.info("This box is currently empty.")

    # =====================================================================
    # WORKFLOW 2: REGISTER & BULK ADD ITEMS
    # =====================================================================
    elif choice == "Register Properties":
        st.subheader("📝 Register & Add Properties")
        tab1, tab2 = st.tabs(["Add Properties to a Box", "Create a New Box"])
        
        with tab2:
            new_box_id = st.text_input("Enter Unique Box ID (e.g., BOX-001)").strip().upper()
            box_desc = st.text_area("Box Description / Location Shelf")
            if st.button("Create Box"):
                if new_box_id and new_box_id not in available_boxes:
                    with st.spinner("Creating new box..."):
                        boxes_sheet.append_row([new_box_id, box_desc])
                    st.success(f"Successfully created {new_box_id}!")
                    st.rerun()
                elif new_box_id in available_boxes:
                    st.error("This Box ID already exists!")
                else:
                    st.error("Box ID cannot be empty.")

        with tab1:
            if available_boxes:
                target_box = st.selectbox("📥 Step 1: Select which Box to put properties in", available_boxes)
                
                box_items = items_df[items_df["Box ID"] == target_box]
                if not box_items.empty:
                    with st.expander(f"👁️ View {len(box_items)} items already inside {target_box}"):
                        view_df = box_items.copy()
                        view_df["CR Number"] = view_df["FIR Number"].astype(str) + "/" + view_df["FIR Year"].astype(str)
                        st.dataframe(view_df[["CR Number", "Type of Article"]], use_container_width=True, hide_index=True)
                else:
                    st.caption(f"📦 {target_box} is currently empty.")
                
                st.markdown("---")
                st.write("### Step 2: Enter Case Details")
                col1, col2, col3, col4, col5 = st.columns([2, 1, 3, 2, 1])
                with col1: fir_no = st.text_input("FIR Number")
                with col2: fir_year = st.text_input("FIR Year", value="2026")
                with col3: sec_law = st.text_input("Section of Law")
                with col4: pf_no = st.text_input("PF Number")
                with col5: pf_year = st.text_input("PF Year", value="2026")
                    
                st.markdown("### Step 3: Add Properties for this Case")
                item_name = st.text_input("Type of Article (e.g., 1 Black Wallet, Vivo Mobile Phone)")
                
                if st.button("➕ Add Property"):
                    if fir_no and item_name and pf_no:
                        st.session_state.pending_items.append({
                            "FIR No": fir_no, "FIR Year": fir_year, "Section": sec_law,
                            "PF No": pf_no, "PF Year": pf_year, "Article": item_name
                        })
                        st.success(f"Added '{item_name}'! You can add another below.")
                    else:
                        st.error("FIR Number, PF Number, and Type of Article are mandatory.")
                
                if st.session_state.pending_items:
                    st.markdown("---")
                    st.write(f"### 📋 Pending Properties to be saved to {target_box}")
                    
                    display_df = pd.DataFrame(st.session_state.pending_items)
                    edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True)
                    
                    colA, colB = st.columns([1, 4])
                    with colA:
                        if st.button("💾 SAVE ALL TO CLOUD", type="primary"):
                            with st.spinner("Saving properties to Google Sheets..."):
                                next_id = get_next_item_id(items_sheet)
                                rows_to_add = []
                                for index, row in edited_df.iterrows():
                                    rows_to_add.append([
                                        next_id, target_box, row["FIR No"], row["FIR Year"], 
                                        row["Section"], row["PF No"], row["PF Year"], 
                                        row["Article"], "In Room"
                                    ])
                                    next_id += 1
                                items_sheet.append_rows(rows_to_add)
                                
                            st.session_state.pending_items = []
                            st.success(f"All properties securely saved!")
                            st.rerun()
                    with colB:
                        if st.button("Clear List"):
                            st.session_state.pending_items = []
                            st.rerun()
            else:
                st.info("Please create a box in the 'Create a New Box' tab first.")

    # =====================================================================
    # WORKFLOW 3: MOVE PROPERTY BETWEEN BOXES
    # =====================================================================
    elif choice == "Move Property":
        st.subheader("🚛 Bulk Move Properties Between Boxes")
        
        if len(available_boxes) > 1:
            source_box = st.selectbox("1️⃣ Select the Current Box (Where properties are now)", available_boxes)
            
            box_items = items_df[items_df["Box ID"] == source_box].copy()
            
            if not box_items.empty:
                st.write(f"### Select Properties inside {source_box} to move:")
                
                box_items["CR Number"] = box_items["FIR Number"].astype(str) + "/" + box_items["FIR Year"].astype(str)
                box_items.insert(0, "Select to Move", False)
                
                edited_items_df = st.data_editor(
                    box_items[["Select to Move", "Item ID", "CR Number", "Type of Article", "Status"]],
                    hide_index=True,
                    column_config={"Select to Move": st.column_config.CheckboxColumn(required=True)},
                    disabled=["Item ID", "CR Number", "Type of Article", "Status"], 
                    use_container_width=True
                )
                
                selected_items = edited_items_df[edited_items_df["Select to Move"] == True]
                
                if not selected_items.empty:
                    st.write(f"**You have selected {len(selected_items)} property(ies) to move.**")
                    
                    destination_boxes = [b for b in available_boxes if b != source_box]
                    new_box = st.selectbox("2️⃣ Select Destination Box", destination_boxes)
                    
                    if st.button(f"🚀 Move Selected Properties to {new_box}", type="primary"):
                        with st.spinner("Moving items in cloud..."):
                            for index, row in selected_items.iterrows():
                                item_id = row["Item ID"]
                                row_idx = get_row_by_item_id(items_sheet, item_id)
                                items_sheet.update_cell(row_idx, 2, new_box) # Column 2 is Box ID
                        st.success(f"Successfully moved items to {new_box}!")
                        st.rerun()
            else:
                st.info(f"{source_box} is currently empty.")
        else:
            st.info("You need at least two boxes created to use the move feature.")

    # =====================================================================
    # WORKFLOW 4: EDIT / DELETE EXISTING RECORDS
    # =====================================================================
    elif choice == "Edit / Delete Records":
        st.subheader("🛠️ Edit or Permanently Delete Records")
        
        if available_boxes:
            target_box = st.selectbox("1️⃣ Find property located in Box:", available_boxes)
            
            box_items = items_df[items_df["Box ID"] == target_box].copy()
            
            if not box_items.empty:
                box_items["Full FIR"] = box_items["FIR Number"].astype(str) + " / " + box_items["FIR Year"].astype(str)
                fir_list = box_items["Full FIR"].unique().tolist()
                
                selected_fir = st.selectbox("2️⃣ Select FIR Number in this Box:", fir_list)
                
                f_no, f_year = selected_fir.split(" / ")
                
                fir_items = box_items[(box_items["FIR Number"].astype(str) == f_no) & (box_items["FIR Year"].astype(str) == f_year)]
                
                if not fir_items.empty:
                    st.write(f"### 🔍 Properties under CR {selected_fir} in {target_box}:")
                    st.markdown("---")
                    
                    for index, row in fir_items.iterrows():
                        item_id = row['Item ID']
                        
                        col1, col2 = st.columns([6, 1])
                        with col1:
                            st.markdown(f"**Item ID {item_id}:** {row['Type of Article']} (PF: {row['PF Number']}/{row['PF Year']}, Sec: {row['Section of Law']})")
                        with col2:
                            if st.button("🗑️ Delete", key=f"del_{item_id}"):
                                with st.spinner("Deleting record..."):
                                    row_idx = get_row_by_item_id(items_sheet, item_id)
                                    items_sheet.delete_rows(row_idx)
                                st.rerun()
                        
                        with st.expander(f"📝 Edit Details for Item {item_id}"):
                            colA, colB, colC, colD, colE = st.columns([2, 1, 3, 2, 1])
                            with colA: e_fir = st.text_input("FIR Number", value=row['FIR Number'], key=f"f_{item_id}")
                            with colB: e_fir_year = st.text_input("FIR Year", value=row['FIR Year'], key=f"fy_{item_id}")
                            with colC: e_sec = st.text_input("Section of Law", value=row['Section of Law'], key=f"s_{item_id}")
                            with colD: e_pf = st.text_input("PF Number", value=row['PF Number'], key=f"p_{item_id}")
                            with colE: e_pf_year = st.text_input("PF Year", value=row['PF Year'], key=f"py_{item_id}")
                                
                            e_item_name = st.text_input("Type of Article", value=row['Type of Article'], key=f"n_{item_id}")
                            
                            if st.button("💾 Save Changes", type="primary", key=f"save_{item_id}"):
                                with st.spinner("Saving edits..."):
                                    row_idx = get_row_by_item_id(items_sheet, item_id)
                                    items_sheet.update_cell(row_idx, 3, e_fir)
                                    items_sheet.update_cell(row_idx, 4, e_fir_year)
                                    items_sheet.update_cell(row_idx, 5, e_sec)
                                    items_sheet.update_cell(row_idx, 6, e_pf)
                                    items_sheet.update_cell(row_idx, 7, e_pf_year)
                                    items_sheet.update_cell(row_idx, 8, e_item_name)
                                st.success("Record updated successfully!")
                                st.rerun()
                        
                        st.markdown("---")
            else:
                st.info(f"No properties are currently stored in {target_box}.")
        else:
            st.info("No boxes available.")

    # =====================================================================
    # WORKFLOW 5: GENERATE QR CODES (FOR BOXES & INDIVIDUAL PROPERTIES)
    # =====================================================================
    elif choice == "Generate QR Codes":
        st.subheader("🖨️ Print Static QR Codes")
        
        public_url = st.text_input("Streamlit App Link", value="https://your-app-name.streamlit.app").rstrip('/')
        
        qr_type = st.radio("Generate QR For:", ["Storage Box ID Link", "Specific Property Entry ID Link"])
        
        if qr_type == "Storage Box ID Link":
            if available_boxes:
                selected_qr_box = st.selectbox("Select Box to generate QR", available_boxes)
                qr_url = f"{public_url}/?box_id={selected_qr_box}"
                file_name_out = f"QR_{selected_qr_box}.png"
            else:
                st.info("No boxes available.")
                qr_url = None
        else:
            if not items_df.empty:
                item_options = items_df.set_index('Item ID')
                selected_qr_item = st.selectbox("Select Item Reference to generate QR Details Page", items_df['Item ID'].tolist())
                qr_url = f"{public_url}/?item_id={selected_qr_item}"
                file_name_out = f"QR_ITEM_{selected_qr_item}.png"
            else:
                st.info("No property records added yet.")
                qr_url = None

        if qr_url:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption=f"QR Target: {qr_url}", width=250)
            
            st.download_button(
                label="Download QR Sticker",
                data=buf.getvalue(),
                file_name=file_name_out,
                mime="image/png"
            )
