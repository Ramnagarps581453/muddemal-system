import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO
from PIL import Image
import socket
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# --- AUTO IP DETECTOR ---
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

# --- GOOGLE SHEETS SETUP ---
@st.cache_resource
def init_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    except Exception:
        creds_dict = json.loads(st.secrets["google_secret"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
    client = gspread.authorize(creds)
    sheet = client.open("Muddemal_Database")
    return sheet.worksheet("Boxes"), sheet.worksheet("Items")

boxes_sheet, items_sheet = init_gsheets()

# --- HELPER FUNCTIONS ---
def get_row_by_item_id(sheet, item_id):
    col_values = sheet.col_values(1)
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

# Helper function to inject spaces after punctuation to force text wrapping
def clean_text_for_wrap(text):
    text_str = str(text)
    # Adds a space after commas if there isn't one
    text_str = text_str.replace(",", ", ")
    # Adds a space around hyphens for long descriptions like slip-01
    text_str = text_str.replace("-", " - ")
    # Clean up double spaces caused by replacement
    return " ".join(text_str.split())

# --- STREAMLIT INTERFACE ---
st.set_page_config(page_title="Ramanagar PS Muddemal System", layout="wide")

# --- CUSTOM CSS FOR BOTH SCREEN WRAPPING AND PRINT LAYOUT ---
st.markdown("""
    <style>
    /* Global Screen Table Styling to force true multi-line text wrapping */
    .screen-table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
        font-family: sans-serif;
        background-color: white;
        border-radius: 6px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        table-layout: fixed; /* Forces column widths to be strictly obeyed */
    }
    .screen-table th {
        background-color: #f1f3f6;
        color: #333333;
        font-weight: 600;
        text-align: left;
        padding: 12px;
        border-bottom: 2px solid #dee2e6;
        font-size: 14px;
    }
    .screen-table td {
        padding: 12px;
        border-bottom: 1px solid #dee2e6;
        color: #212529;
        font-size: 14px;
        vertical-align: top;
        
        /* POWERFUL CSS TO FORCE BOX WRAPPING AT ALL COSTS */
        white-space: normal !important; 
        word-wrap: break-word !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }
    .screen-table tr:hover {
        background-color: #f8f9fa;
    }
    .kannada-text {
        font-size: 15px;
        line-height: 1.5;
    }

    /* Print Specific Media Styles */
    @media print {
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="stHeader"] {display: none !important;}
        footer {visibility: hidden !important;}
        .no-print {display: none !important;}
        button {display: none !important;}
        [data-testid="stMetricWidget"] {display: none !important;}
        .stMainBlockContainer {padding: 0rem !important; margin: 0rem !important; max-width: 100% !important;}
        
        .screen-table { display: none !important; } 
        
        .print-container {
            display: block !important;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #000000 !important;
        }
        .print-title {
            color: #1A237E !important;
            font-size: 26px !important;
            font-weight: bold !important;
            text-align: center !important;
            margin-bottom: 5px !important;
            text-transform: uppercase !important;
        }
        .print-subtitle {
            text-align: center !important;
            font-size: 14px !important;
            color: #444 !important;
            margin-bottom: 25px !important;
        }
        .print-grid { width: 100%; border-collapse: collapse; margin-top: 10px; table-layout: fixed; }
        .print-grid th { 
            background-color: #1A237E !important; 
            color: white !important;
            -webkit-print-color-adjust: exact; 
            print-color-adjust: exact; 
            padding: 10px;
            font-size: 14px;
            border: 1px solid #1A237E;
        }
        .print-grid td {
            color: #000000 !important;
            border: 1px solid #000000 !important;
            padding: 10px;
            font-size: 14px;
            vertical-align: top;
            white-space: normal !important;
            word-wrap: break-word !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }
    }
    
    /* Screen Fallbacks for Hidden Print Elements */
    .print-container { display: none; }
    .print-title { color: #1A237E; font-size: 24px; font-weight: bold; text-align: center; margin-bottom: 5px; text-transform: uppercase; }
    .print-subtitle { text-align: center; font-size: 14px; color: #555; margin-bottom: 25px; font-weight: 500; }
    .print-meta-table { width: 100%; margin-bottom: 20px; font-size: 15px; }
    .zebra { background-color: #F9F9F9; }
    </style>
""", unsafe_allow_html=True)

# Standard Dashboard Branding Headers
st.markdown("<h1 style='text-align: center;' class='no-print'>Ramanagar Police Station Muddemal Digital Record Room</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;' class='no-print'><em>(Connected to Secure Google Cloud)</em></p>", unsafe_allow_html=True)
st.markdown("<hr class='no-print'>", unsafe_allow_html=True)

# --- READ QUERY PARAMETERS FOR QR SCANNING ---
query_params = st.query_params
scanned_box = query_params.get("box_id", None)

# --- SIDEBAR SEARCH & NAVIGATION ---
st.sidebar.header("🔍 Property Search")
search_query = st.sidebar.text_input("Search FIR, PF, or Article Name").strip().lower()

st.sidebar.markdown("---")
menu = ["View & Update Box", "Register Properties", "Move Property", "Edit / Delete Records", "Generate QR Codes"]
choice = st.sidebar.selectbox("Navigation Menu", menu, index=0)

if scanned_box:
    if st.sidebar.button("🔄 Clear Scanned Box Filter"):
        st.query_params.clear()
        st.rerun()

# --- DATABASE SYNC ---
with st.spinner("Syncing with Google Database..."):
    b_data = boxes_sheet.get_all_records()
    i_data = items_sheet.get_all_records()
    boxes_df = pd.DataFrame(b_data) if b_data else pd.DataFrame(columns=["Box ID", "Description"])
    items_df = pd.DataFrame(i_data) if i_data else pd.DataFrame(columns=["Item ID", "Box ID", "FIR Number", "FIR Year", "Section of Law", "PF Number", "PF Year", "Type of Article", "Status"])
    available_boxes = boxes_df["Box ID"].tolist() if not boxes_df.empty else []

# --- RENDER GLOBAL SEARCH RESULTS ---
if search_query:
    st.subheader(f"🔎 Search Results for: '{search_query}'")
    filtered_df = items_df[
        items_df["FIR Number"].astype(str).str.lower().str.contains(search_query) |
        items_df["PF Number"].astype(str).str.lower().str.contains(search_query) |
        items_df["Type of Article"].astype(str).str.lower().str.contains(search_query)
    ].copy()
    
    if not filtered_df.empty:
        filtered_df["CR Number"] = filtered_df["FIR Number"].astype(str) + "/" + filtered_df["FIR Year"].astype(str)
        filtered_df["PF Number Formatted"] = filtered_df["PF Number"].astype(str) + "/" + filtered_df["PF Year"].astype(str)
        
        search_html = """<table class="screen-table"><thead><tr><th style="width: 8%;">Item ID</th><th style="width: 10%;">Box ID</th><th style="width: 12%;">CR Number</th><th style="width: 23%;">Section of Law</th><th style="width: 12%;">PF Number</th><th style="width: 25%;">Type of Article</th><th style="width: 10%;">Status</th></tr></thead><tbody>"""
        for _, row in filtered_df.iterrows():
            sec_clean = clean_text_for_wrap(row['Section of Law'])
            art_clean = clean_text_for_wrap(row['Type of Article'])
            search_html += f"""<tr><td>{row['Item ID']}</td><td>{row['Box ID']}</td><td>{row['CR Number']}</td><td>{sec_clean}</td><td>{row['PF Number Formatted']}</td><td class="kannada-text">{art_clean}</td><td>{row['Status']}</td></tr>"""
        search_html += "</tbody></table>"
        st.markdown(search_html, unsafe_allow_html=True)
    else:
        st.info("No matching records found across any box.")
    st.markdown("---")

# =====================================================================
# WORKFLOW 1: VIEW & UPDATE BOX
# =====================================================================
if choice == "View & Update Box":
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
            display_df = box_items.copy()
            display_df["CR Number"] = display_df["FIR Number"].astype(str) + "/" + display_df["FIR Year"].astype(str)
            display_df["PF Number"] = display_df["PF Number"].astype(str) + "/" + display_df["PF Year"].astype(str)
            
            st.markdown(f"### Properties currently inside **{box_id}**:")
            
            screen_html = """
            <table class="screen-table no-print">
                <thead>
                    <tr>
                        <th style="width: 8%;">Item ID</th>
                        <th style="width: 12%;">CR Number</th>
                        <th style="width: 23%;">Section of Law</th>
                        <th style="width: 12%;">PF Number</th>
                        <th style="width: 35%;">Type of Article</th>
                        <th style="width: 10%;">Status</th>
                    </tr>
                </thead>
                <tbody>
            """
            for _, row in display_df.iterrows():
                # Process fields through the clean-wrapper text rule right before rendering
                clean_section = clean_text_for_wrap(row['Section of Law'])
                clean_article = clean_text_for_wrap(row['Type of Article'])
                
                screen_html += f"""
                    <tr>
                        <td><strong>{row['Item ID']}</strong></td>
                        <td>{row['CR Number']}</td>
                        <td>{clean_section}</td>
                        <td>{row['PF Number']}</td>
                        <td class="kannada-text">{clean_article}</td>
                        <td>{row['Status']}</td>
                    </tr>
                """
            screen_html += "</tbody></table>"
            st.markdown(screen_html, unsafe_allow_html=True)
            
            # --- INVISIBLE PRINT LAYOUT GENERATION ---
            timestamp = pd.Timestamp.now().strftime('%d-%m-%Y %I:%M %p')
            html_output = f"""
            <div class="print-container">
                <div class="print-title">Ramanagar Police Station Muddemal Inventory</div>
                <div class="print-subtitle">Official Record Room Storage Manifest</div>
                <table class="print-meta-table">
                    <tr>
                        <td><strong>Box Reference ID:</strong> {box_id}</td>
                        <td style="text-align: right;"><strong>Generated On:</strong> {timestamp}</td>
                    </tr>
                </table>
                <table class="print-grid">
                    <thead>
                        <tr>
                            <th style="width: 8%;">Item ID</th>
                            <th style="width: 14%;">CR / FIR No.</th>
                            <th style="width: 23%;">Section of Law</th>
                            <th style="width: 13%;">PF Number</th>
                            <th style="width: 32%;">Property Description</th>
                            <th style="width: 10%;">Current Status</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for idx, row in display_df.reset_index().iterrows():
                bg_class = 'class="zebra"' if idx % 2 == 0 else ''
                print_section = clean_text_for_wrap(row["Section of Law"])
                print_article = clean_text_for_wrap(row["Type of Article"])
                
                html_output += f"""
                        <tr {bg_class}>
                            <td>{str(row["Item ID"])}</td>
                            <td>{str(row["CR Number"])}</td>
                            <td>{print_section}</td>
                            <td>{str(row["PF Number"])}</td>
                            <td class="kannada-text">{print_article}</td>
                            <td>{str(row["Status"])}</td>
                        </tr>
                """
            html_output += """
                    </tbody>
                </table>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)
            
            st.markdown("---")
            st.info("💡 **Print Instructions:** Need a physical backup manifest? Simply press **Ctrl + P** (or **Cmd + P** on Mac) right now. The page will cleanly isolate just the Kannada ledger sheet table automatically.")
        else:
            st.info("This box is currently empty.")

# =====================================================================
# WORKFLOW 2: REGISTER & BULK ADD ITEMS
# =====================================================================
elif choice == "Register Properties":
    st.subheader("Register & Add Properties")
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
            target_box = st.selectbox("Step 1: Select which Box to put properties in", available_boxes)
            
            box_items = items_df[items_df["Box ID"] == target_box]
            if not box_items.empty:
                with st.expander(f"View {len(box_items)} items already inside {target_box}"):
                    view_df = box_items.copy()
                    view_df["CR Number"] = view_df["FIR Number"].astype(str) + "/" + view_df["FIR Year"].astype(str)
                    
                    sub_table = """<table class="screen-table"><thead><tr><th style="width: 30%;">CR Number</th><th style="width: 70%;">Type of Article</th></tr></thead><tbody>"""
                    for _, row in view_df.iterrows():
                        clean_art_view = clean_text_for_wrap(row['Type of Article'])
                        sub_table += f"""<tr><td>{row['CR Number']}</td><td class="kannada-text">{clean_art_view}</td></tr>"""
                    sub_table += "</tbody></table>"
                    st.markdown(sub_table, unsafe_allow_html=True)
            else:
                st.caption(f"{target_box} is currently empty.")
            
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
            
            if st.button("Add Property"):
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
                st.write(f"### Pending Properties to be saved to {target_box}")
                
                display_df = pd.DataFrame(st.session_state.pending_items)
                edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True)
                
                colA, colB = st.columns([1, 4])
                with colA:
                    if st.button("SAVE ALL TO CLOUD", type="primary"):
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
# WORKFLOW 3: MOVE PROPERTY
# =====================================================================
elif choice == "Move Property":
    st.subheader("Bulk Move Properties Between Boxes")
    
    if len(available_boxes) > 1:
        source_box = st.selectbox("Select the Current Box (Where properties are now)", available_boxes)
        box_items = items_df[items_df["Box ID"] == source_box].copy()
        
        if not box_items.empty:
            st.write(f"### Select Properties inside {source_box} to move:")
            box_items["CR Number"] = box_items["FIR Number"].astype(str) + "/" + box_items["FIR Year"].astype(str)
            box_items.insert(0, "Select to Move", False)
            
            edited_items_df = st.data_editor(
                box_items[["Select to Move", "Item ID", "CR Number", "Type of Article", "Status"]],
                hide_index=True,
                column_config={
                    "Select to Move": st.column_config.CheckboxColumn(required=True),
                },
                disabled=["Item ID", "CR Number", "Type of Article", "Status"], 
                use_container_width=True
            )
            
            selected_items = edited_items_df[edited_items_df["Select to Move"] == True]
            
            if not selected_items.empty:
                st.write(f"**You have selected {len(selected_items)} property(ies) to move.**")
                destination_boxes = [b for b in available_boxes if b != source_box]
                new_box = st.selectbox("Select Destination Box", destination_boxes)
                
                if st.button(f"Move Selected Properties to {new_box}", type="primary"):
                    with st.spinner("Moving items in cloud..."):
                        for index, row in selected_items.iterrows():
                            item_id = row["Item ID"]
                            row_idx = get_row_by_item_id(items_sheet, item_id)
                            items_sheet.update_cell(row_idx, 2, new_box)
                    st.success(f"Successfully moved items to {new_box}!")
                    st.rerun()
        else:
            st.info(f"{source_box} is currently empty.")
    else:
        st.info("You need at least two boxes created to use the move feature.")

# =====================================================================
# WORKFLOW 4: EDIT / DELETE
# =====================================================================
elif choice == "Edit / Delete Records":
    st.subheader("Edit or Permanently Delete Records")
    if available_boxes:
        target_box = st.selectbox("Find property located in Box:", available_boxes)
        box_items = items_df[items_df["Box ID"] == target_box].copy()
        
        if not box_items.empty:
            box_items["Full FIR"] = box_items["FIR Number"].astype(str) + " / " + box_items["FIR Year"].astype(str)
            fir_list = box_items["Full FIR"].unique().tolist()
            selected_fir = st.selectbox("Select FIR Number in this Box:", fir_list)
            
            f_no, f_year = selected_fir.split(" / ")
            fir_items = box_items[(box_items["FIR Number"].astype(str) == f_no) & (box_items["FIR Year"].astype(str) == f_year)]
            
            if not fir_items.empty:
                st.write(f"### Properties under CR {selected_fir} in {target_box}:")
                st.markdown("---")
                
                for index, row in fir_items.iterrows():
                    item_id = row['Item ID']
                    col1, col2 = st.columns([6, 1])
                    with col1:
                        st.markdown(f"**Item ID {item_id}:** {row['Type of Article']} (PF: {row['PF Number']}/{row['PF Year']}, Sec: {row['Section of Law']}) | *Current Status: {row['Status']}*")
                    with col2:
                        if st.button("Delete", key=f"del_{item_id}"):
                            with st.spinner("Deleting record..."):
                                row_idx = get_row_by_item_id(items_sheet, item_id)
                                items_sheet.delete_rows(row_idx)
                            st.rerun()
                    
                    with st.expander(f"Edit Details & Status for Item {item_id}"):
                        colA, colB, colC, colD, colE = st.columns([2, 1, 3, 2, 1])
                        with colA: e_fir = st.text_input("FIR Number", value=row['FIR Number'], key=f"f_{item_id}")
                        with colB: e_fir_year = st.text_input("FIR Year", value=row['FIR Year'], key=f"fy_{item_id}")
                        with colC: e_sec = st.text_input("Section of Law", value=row['Section of Law'], key=f"s_{item_id}")
                        with colD: e_pf = st.text_input("PF Number", value=row['PF Number'], key=f"p_{item_id}")
                        with colE: e_pf_year = st.text_input("PF Year", value=row['PF Year'], key=f"py_{item_id}")
                            
                        e_item_name = st.text_input("Type of Article", value=row['Type_of_Article'] if 'Type_of_Article' in row else row.get('Type of Article', ''), key=f"n_{item_id}")
                        e_status = st.selectbox("Change Status", ["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"], index=["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"].index(row['Status']) if row['Status'] in ["In Room", "Submitted to Court with Charge Sheet", "Released to Owner", "Sent to FSL", "Disposed / Destroyed"] else 0, key=f"st_{item_id}")
                        
                        if st.button("Save Changes", type="primary", key=f"save_{item_id}"):
                            with st.spinner("Saving edits..."):
                                row_idx = get_row_by_item_id(items_sheet, item_id)
                                items_sheet.update_cell(row_idx, 3, e_fir)
                                items_sheet.update_cell(row_idx, 4, e_fir_year)
                                items_sheet.update_cell(row_idx, 5, e_sec)
                                items_sheet.update_cell(row_idx, 6, e_pf)
                                items_sheet.update_cell(row_idx, 7, e_pf_year)
                                items_sheet.update_cell(row_idx, 8, e_item_name)
                                items_sheet.update_cell(row_idx, 9, e_status)
                            st.success("Record updated successfully!")
                            st.rerun()
                    st.markdown("---")
        else:
            st.info(f"No properties are currently stored in {target_box}.")
    else:
        st.info("No boxes available.")

# =====================================================================
# WORKFLOW 5: GENERATE QR CODES
# =====================================================================
elif choice == "Generate QR Codes":
    st.subheader("🖨️ Print Static Box QR Codes")
    public_url = "https://muddemal-system-s3e4dhhy2wdwpsbxhsjxyr.streamlit.app"
    if public_url.endswith("/"):
        public_url = public_url[:-1]
        
    if available_boxes:
        selected_qr_box = st.selectbox("Select Box to generate QR", available_boxes)
        st.info(f"### Generating QR Code Matrix for: {selected_qr_box}")
        
        qr_url = f"{public_url}/?box_id={selected_qr_box}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption=f"QR Code Link: {qr_url}", width=250)
        
        st.markdown(f"🔗 **[Click here to test opening this box's link]({qr_url})**")
        st.download_button(
            label=f"Download QR Code Sticker for {selected_qr_box}",
            data=buf.getvalue(),
            file_name=f"QR_{selected_qr_box}.png",
            mime="image/png"
        )
    else:
        st.info("No boxes available to generate QR codes.")
