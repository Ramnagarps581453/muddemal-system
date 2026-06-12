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

# --- REPORTLAB IMPORTS FOR STABLE PDF HANDLING ---
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    st.error("Please add 'reportlab' to your requirements.txt file to enable proper PDF downloading.")

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

# --- REPORTLAB KANNADA PDF GENERATOR ---
def generate_box_pdf(box_id, dataframe):
    buffer = BytesIO()
    
    # Initialize Document in Landscape
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(letter),
        leftMargin=30, 
        rightMargin=30, 
        topMargin=30, 
        bottomMargin=30
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Register Kannada font if file exists
    FONT_PATH = "NotoSansKannada-Regular.ttf"
    font_name = "Helvetica"
    if os.path.exists(FONT_PATH):
        try:
            pdfmetrics.registerFont(TTFont('KannadaFont', FONT_PATH))
            font_name = "KannadaFont"
        except Exception:
            pass

    # Custom paragraph style rules
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor("#1A237E"),
        alignment=1, # Center
        spaceAfter=10
    )
    
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        spaceAfter=15
    )
    
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.white,
        alignment=1 # Center
    )
    
    body_cell_style = ParagraphStyle(
        'BodyCell',
        fontName=font_name,
        fontSize=10,
        leading=14
    )

    # Build Header Elements
    story.append(Paragraph("RAMANAGAR POLICE STATION MUDDEMAL INVENTORY", title_style))
    timestamp = pd.Timestamp.now().strftime('%d-%m-%Y %I:%M %p')
    meta_text = f"<b>Box Reference ID:</b> {box_id}<br/><b>Generated On:</b> {timestamp}"
    story.append(Paragraph(meta_text, meta_style))
    
    # Define Column Headers & Widths (Total 730 points for landscape letter width)
    headers = ["Item ID", "CR / FIR No.", "Section of Law", "PF Number", "Property Description", "Current Status"]
    col_widths = [45, 95, 120, 95, 260, 115]
    
    table_data = []
    
    # Wrap header texts inside Paragraph flowables
    header_row = [Paragraph(f"<b>{h}</b>", header_cell_style) for h in headers]
    table_data.append(header_row)
    
    # Wrap database table contents
    for idx, row in dataframe.iterrows():
        table_data.append([
            Paragraph(str(row["Item ID"]), body_cell_style),
            Paragraph(str(row["CR Number"]), body_cell_style),
            Paragraph(str(row["Section of Law"]), body_cell_style),
            Paragraph(str(row["PF Number"]), body_cell_style),
            Paragraph(str(row["Type of Article"]), body_cell_style), # Kannada font gets safely rendered here
            Paragraph(str(row["Status"]), body_cell_style)
        ])
        
    # Build and style ReportLab data grid table structure
    data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A237E")),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#1A237E")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])
    
    # Add Zebra stripe alternate styling row backgrounds safely
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F5F5F5"))
            
    data_table.setStyle(t_style)
    story.append(data_table)
    
    # Render full sequence array stream
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- STREAMLIT INTERFACE ---
st.set_page_config(page_title="Ramanagar PS Muddemal System", layout="wide")

st.markdown("<h1 style='text-align: center;'>Ramanagar Police Station Muddemal Digital Record Room</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'><em>(Connected to Secure Google Cloud)</em></p>", unsafe_allow_html=True)
st.markdown("---")

query_params = st.query_params
scanned_box = query_params.get("box_id", None)

# --- SIDEBAR SEARCH & NAVIGATION ---
st.sidebar.header("🔍 Property Search")
search_query = st.sidebar.text_input("Search FIR, PF, or Article Name").strip().lower()

st.sidebar.markdown("---")
menu = ["View & Update Box", "Register Properties", "Move Property", "Edit / Delete Records", "Generate QR Codes"]
choice = st.sidebar.selectbox("Navigation Menu", menu, index=0 if scanned_box else 0)

with st.spinner("Syncing with Google Database..."):
    b_data = boxes_sheet.get_all_records()
    i_data = items_sheet.get_all_records()
    boxes_df = pd.DataFrame(b_data) if b_data else pd.DataFrame(columns=["Box ID", "Description"])
    items_df = pd.DataFrame(i_data) if i_data else pd.DataFrame(columns=["Item ID", "Box ID", "FIR Number", "FIR Year", "Section of Law", "PF Number", "PF Year", "Type of Article", "Status"])

    available_boxes = boxes_df["Box ID"].tolist() if not boxes_df.empty else []

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
        display_search = filtered_df[["Item ID", "Box ID", "CR Number", "Section of Law", "PF Number Formatted", "Type of Article", "Status"]]
        st.dataframe(display_search.set_index('Item ID'), use_container_width=True)
    else:
        st.info("No matching records found across any box.")
    st.markdown("---")

# WORKFLOW 1: VIEW ITEMS
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
            raw_pdf_df = display_df.copy()
            
            display_df = display_df[["Item ID", "CR Number", "Section of Law", "PF Number", "Type of Article", "Status"]]
            st.dataframe(display_df.set_index('Item ID'), use_container_width=True)
            
            try:
                pdf_data = generate_box_pdf(box_id, raw_pdf_df)
                st.download_button(
                    label=f"📥 Download Detailed PDF Inventory ({box_id})",
                    data=pdf_data,
                    file_name=f"Inventory_{box_id}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"PDF Generation error: {e}")
        else:
            st.info("This box is currently empty.")

# WORKFLOW 2: REGISTER & BULK ADD ITEMS
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
                    st.dataframe(view_df[["CR Number", "Type of Article"]], use_container_width=True, hide_index=True)
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

# WORKFLOW 3: MOVE PROPERTY
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
                column_config={"Select to Move": st.column_config.CheckboxColumn(required=True)},
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

# WORKFLOW 4: EDIT / DELETE
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
                            
                        e_item_name = st.text_input("Type of Article", value=row['Type of Article'], key=f"n_{item_id}")
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

# WORKFLOW 5: GENERATE QR CODES
elif choice == "Generate QR Codes":
    st.subheader("🖨️ Print Static Box QR Codes")
    public_url = "https://muddemal-system-s3e4dhhy2wdwpsbxhsjxyr.streamlit.app/"
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
