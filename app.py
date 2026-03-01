import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "2.3"
DATE_FILE = datetime.now().strftime("%d_%m_%Y")
DB_PATH = 'gv2_data.db'

FORCED_COLORS = {
    "JC": "#E22F2F", "Ludo": "#2A33C3", "Nico": "#20DC46",
    "Skydiving Promotion": "#161515", "Sourse": "#C03BD6", "Stemme Belgium": "#999999"
}

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prestations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, collab TEXT, client TEXT, 
                  description TEXT, mission_ref TEXT, temps REAL, 
                  tarif_client REAL, fact_client REAL, 
                  tarif_interne REAL, fact_interne REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, tarif_defaut REAL, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()

init_db()

# --- FONCTIONS UTILITAIRES ---
def get_color_map():
    conn = get_connection()
    collabs_db = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    clients_db = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([collabs_db, clients_db]).dropna(subset=['couleur']).set_index('nom')['couleur'].to_dict()
    return {**db_colors, **FORCED_COLORS}

def reset_form():
    for k in ["f_date", "f_client", "f_collab", "f_temps", "f_desc", "f_ref"]:
        if k in st.session_state:
            st.session_state[k] = None if k == "f_date" else "" if k != "f_temps" else 0.0
    if "submitted" in st.session_state:
        del st.session_state["submitted"]

@st.dialog("⚠️ RESTAURATION")
def confirm_restore_dialog(uploaded_file):
    st.error("### ATTENTION : ÉCRASEMENT DES DONNÉES")
    if st.button("🔥 CONFIRMER", type="primary", use_container_width=True):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Base restaurée !"); st.rerun()

@st.dialog("🗑️ SUPPRESSION")
def confirm_delete_dialog(ids):
    st.warning(f"Supprimer {len(ids)} prestation(s) ?")
    if st.button("OUI, SUPPRIMER", type="primary", use_container_width=True):
        conn = get_connection()
        conn.executemany("DELETE FROM prestations WHERE id = ?", [(x,) for x in ids])
        conn.commit(); st.rerun()

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres"])

# --- 1. ENCODAGE ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    clients_list = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    collabs_list = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()

    if st.session_state.get("submitted"):
        st.success("✅ Enregistré !")
        if st.button("➕ Saisir une autre prestation"): reset_form(); st.rerun()
    else:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                d = st.date_input("Date", value=None, format="DD/MM/YYYY", key="f_date")
                cli = st.selectbox("Client", clients_list, key="f_client")
                col = st.selectbox("Collaborateur", collabs_list, key="f_collab")
            with c2:
                t = st.number_input("Temps (h)", min_value=0.0, step=0.25, key="f_temps")
                tc = st.number_input("Tarif Client (€)", value=80.0)
                ti = st.number_input("Tarif Interne (€)", value=45.0)
            desc = st.text_area("Description", key="f_desc")
            ref = st.text_input("Référence Mission", key="f_ref")
            if st.button("🚀 ENREGISTRER", type="primary", use_container_width=True):
                if d and cli and col and t > 0:
                    conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                                 (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                    conn.commit(); st.session_state["submitted"] = True; st.rerun()
                else: st.error("Champs obligatoires manquants.")

# --- 2. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    cmap = get_color_map()
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'], format='%d/%m/%Y', dayfirst=True)
        df['Année'] = df['date_dt'].dt.strftime('%Y')
        df['Mois'] = df['date_dt'].dt.strftime('%m/%Y')
        
        st.sidebar.header("🔍 Filtres")
        y = st.sidebar.multiselect("Années", sorted(df['Année'].unique(), reverse=True), default=df['Année'].unique())
        m = st.sidebar.multiselect("Mois", sorted(df['Mois'].unique(), reverse=True), default=df['Mois'].unique())
        co = st.sidebar.multiselect("Collab", sorted(df['collab'].unique()), default=df['collab'].unique())
        cl = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())
        
        df_f = df[(df['Année'].isin(y)) & (df['Mois'].isin(m)) & (df['collab'].isin(co)) & (df['client'].isin(cl))]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA Client HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge GV2", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            
            # --- AJOUT : EXPORTATION FILTRÉE ---
            csv = df_f.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Exporter cette sélection (CSV)", csv, f"export_gv2_{DATE_FILE}.csv", "text/csv")
            
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=cmap), use_container_width=True)
        else: st.warning("Sélection vide.")
    else: st.info("Base vide.")

# --- 3. GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion des prestations")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    if not df_edit.empty:
        df_edit.insert(0, '🗑️', False)
        edited = st.data_editor(df_edit, disabled=["id"], hide_index=True)
        c1, c2 = st.columns(2)
        if c1.button("💾 Sauvegarder les modifications"):
            for _, r in edited[edited['🗑️'] == False].iterrows():
                conn.execute("UPDATE prestations SET date=?, collab=?, client=?, description=?, temps=? WHERE id=?", (r['date'], r['collab'], r['client'], r['description'], r['temps'], r['id']))
            conn.commit(); st.success("Données mises à jour !"); st.rerun()
        if not edited[edited['🗑️']].empty and c2.button("🔥 Supprimer sélection"):
            confirm_delete_dialog(edited[edited['🗑️']]['id'].tolist())

# --- 4. PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    
    # Export/Import Complet DB
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("📤 Backup Complet (.db)")
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(f"📥 Télécharger gv2_data_{DATE_FILE}.db", f, f"backup_gv2_{DATE_FILE}.db", use_container_width=True)
    with c2:
        with st.container(border=True):
            st.subheader("📥 Restauration (.db)")
            up = st.file_uploader("Fichier backup_gv2_... .db", type="db")
            if up and st.button("🚀 Restaurer"): confirm_restore_dialog(up)

    st.divider()
    t1, t2 = st.tabs(["👥 Collaborateurs", "🏢 Clients"])
    with t1:
        with st.form("new_co", clear_on_submit=True):
            n = st.text_input("Nom")
            if st.form_submit_button("Ajouter"):
                if n: conn.execute("INSERT INTO collaborateurs (nom, couleur) VALUES (?,?)", (n.strip(), "#3498db")); conn.commit(); st.rerun()
        for r in conn.execute("SELECT id, nom, couleur FROM collaborateurs ORDER BY nom").fetchall():
            cols = st.columns([1, 3, 1])
            new_c = cols[0].color_picker("Col", FORCED_COLORS.get(r[1], r[2]), key=f"c_{r[0]}", label_visibility="collapsed")
            if new_c != FORCED_COLORS.get(r[1], r[2]): conn.execute("UPDATE collaborateurs SET couleur=? WHERE id=?", (new_c, r[0])); conn.commit(); st.rerun()
            cols[1].write(r[1])
            if cols[2].button("🗑️", key=f"dc_{r[0]}"): conn.execute("DELETE FROM collaborateurs WHERE id=?", (r[0],)); conn.commit(); st.rerun()
    with t2:
        with st.form("new_cl", clear_on_submit=True):
            n = st.text_input("Nom Client")
            if st.form_submit_button("Ajouter"):
                if n: conn.execute("INSERT INTO clients (nom, tarif_defaut, couleur) VALUES (?,?,?)", (n.strip(), 80.0, "#e67e22")); conn.commit(); st.rerun()
        for r in conn.execute("SELECT id, nom, couleur FROM clients ORDER BY nom").fetchall():
            cols = st.columns([1, 3, 1])
            new_c = cols[0].color_picker("Col", FORCED_COLORS.get(r[1], r[2]), key=f"l_{r[0]}", label_visibility="collapsed")
            if new_c != FORCED_COLORS.get(r[1], r[2]): conn.execute("UPDATE clients SET couleur=? WHERE id=?", (new_c, r[0])); conn.commit(); st.rerun()
            cols[1].write(r[1])
            if cols[2].button("🗑️", key=f"dl_{r[0]}"): conn.execute("DELETE FROM clients WHERE id=?", (r[0],)); conn.commit(); st.rerun()
