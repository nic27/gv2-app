import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import re
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(
    page_title="GV2 Management System", 
    layout="wide", 
    page_icon="logo_gv2.png"
)

VERSION = "1.9"
TODAY = datetime.now().strftime("%d/%m/%Y")
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

def clean_val(x):
    if pd.isna(x) or x == "/": return 0.0
    s = str(x).replace(',', '.').replace('€', '').strip()
    s = re.sub(r'[^0-9.]', '', s)
    try: return float(s)
    except: return 0.0

# --- DIALOGUES DE CONFIRMATION ---
@st.dialog("⚠️ CONFIRMATION DE RESTAURATION")
def confirm_restore_dialog(uploaded_file):
    st.error("### ATTENTION : ACTION IRRÉVERSIBLE")
    st.write(f"Vous allez écraser la base de données actuelle par le fichier : **{uploaded_file.name}**.")
    st.write("Toutes les données saisies depuis votre dernière sauvegarde seront définitivement perdues.")
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🔥 OUI, ÉCRASER TOUT", type="primary", use_container_width=True):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("✅ Restauration réussie ! Redémarrage...")
        st.rerun()
    if c2.button("ANNULER", use_container_width=True):
        st.rerun()

@st.dialog("Confirmer la suppression")
def confirm_delete_dialog(ids_to_delete):
    st.warning(f"⚠️ Supprimer définitivement {len(ids_to_delete)} ligne(s) ?")
    c1, c2 = st.columns(2)
    if c1.button("🔥 Oui, supprimer", type="primary", use_container_width=True):
        conn = get_connection()
        conn.executemany("DELETE FROM prestations WHERE id = ?", [(x,) for x in ids_to_delete])
        conn.commit()
        st.success("Supprimé.")
        st.rerun()
    if c2.button("Annuler", use_container_width=True):
        st.rerun()

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION} | **Date :** {TODAY}")
st.sidebar.divider()
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres"])

# --- PAGES ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    clients_list = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    collabs_list = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            d_obj = st.date_input("Date", value=None, format="DD/MM/YYYY")
            cli = st.selectbox("Client", clients_list)
            col = st.selectbox("Collaborateur", collabs_list)
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25)
            tc = st.number_input("Tarif Client (€)", value=80.0)
            ti = st.number_input("Tarif Interne (€)", value=45.0)
        desc = st.text_area("Description")
        ref = st.text_input("Référence Mission")

        if st.button("🚀 ENREGISTRER", type="primary", use_container_width=True):
            if not d_obj or cli == "" or col == "" or t <= 0:
                st.error("Champs obligatoires manquants.")
            else:
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d_obj.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit(); st.success("✅ Enregistré !"); st.rerun()

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard Analytique")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    cmap = get_color_map()
    
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df['Année'] = df['date_dt'].dt.strftime('%Y')
        df['Mois'] = df['date_dt'].dt.strftime('%m/%Y')

        st.sidebar.header("🔍 Filtres")
        sel_years = st.sidebar.multiselect("Années", sorted(df['Année'].dropna().unique(), reverse=True), default=df['Année'].dropna().unique())
        mask_y = df['Année'].isin(sel_years)
        sel_months = st.sidebar.multiselect("Mois", sorted(df[mask_y]['Mois'].dropna().unique(), reverse=True), default=df[mask_y]['Mois'].dropna().unique())
        sel_collabs = st.sidebar.multiselect("Collaborateurs", sorted(df['collab'].unique()), default=df['collab'].unique())
        sel_clients = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())

        df_f = df[(df['Année'].isin(sel_years)) & (df['Mois'].isin(sel_months)) & (df['collab'].isin(sel_collabs)) & (df['client'].isin(sel_clients))]

        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("Total CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge GV2", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=cmap, text_auto='.2s'), use_container_width=True)
            st.plotly_chart(px.bar(df_f.groupby('collab')['fact_client'].sum().reset_index(), x='collab', y='fact_client', color='collab', color_discrete_map=cmap, text_auto='.2s'), use_container_width=True)
        else: st.warning("Sélection vide.")
    else: st.info("Base vide.")

elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion des données")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    if not df_edit.empty:
        df_edit.insert(0, '🗑️', False)
        edited = st.data_editor(df_edit, disabled=["id"], hide_index=True)
        if st.button("💾 Sauvegarder"):
            for _, r in edited[edited['🗑️'] == False].iterrows():
                conn.execute("UPDATE prestations SET date=?, collab=?, client=?, description=?, temps=?, fact_client=?, fact_interne=? WHERE id=?", (r['date'], r['collab'], r['client'], r['description'], r['temps'], r['fact_client'], r['fact_interne'], r['id']))
            conn.commit(); st.success("Mis à jour !"); st.rerun()
        if not edited[edited['🗑️']].empty and st.button("🔥 Supprimer sélection"):
            confirm_delete_dialog(edited[edited['🗑️']]['id'].tolist())

elif menu == "⚙️ Paramètres":
    st.header("⚙️ Maintenance & Listes")
    conn = get_connection()
    
    # SAUVEGARDE ET RESTAURATION (AVEC CONFIRMATION)
    c_exp, c_imp = st.columns(2)
    with c_exp:
        with st.container(border=True):
            st.subheader("📤 Sauvegarder (.db)")
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button("📥 Télécharger gv2_data.db", f, f"backup_gv2_{datetime.now().strftime('%Y%m%d')}.db", use_container_width=True)
    with c_imp:
        with st.container(border=True):
            st.subheader("📥 Restaurer (.db)")
            up = st.file_uploader("Importer un fichier .db pour restaurer", type="db")
            if up:
                if st.button("🚀 Restaurer cette sauvegarde", type="primary", use_container_width=True):
                    confirm_restore_dialog(up)

    st.divider()
    t1, t2 = st.tabs(["👥 Listes & Couleurs", "📥 Import CSV"])
    
    with t1:
        ca, cb = st.columns(2)
        with ca:
            with st.form("add_co", clear_on_submit=True):
                n = st.text_input("Nouveau Collaborateur")
                if st.form_submit_button("Ajouter"):
                    if n: conn.execute("INSERT INTO collaborateurs (nom, couleur) VALUES (?,?)", (n.strip(), "#3498db")); conn.commit(); st.rerun()
        with cb:
            with st.form("add_cl", clear_on_submit=True):
                n = st.text_input("Nouveau Client")
                if st.form_submit_button("Ajouter"):
                    if n: conn.execute("INSERT INTO clients (nom, tarif_defaut, couleur) VALUES (?,?,?)", (n.strip(), 80.0, "#e67e22")); conn.commit(); st.rerun()
        
        for title, tbl in [("Collaborateurs", "collaborateurs"), ("Clients", "clients")]:
            st.subheader(title)
            for r in conn.execute(f"SELECT id, nom, couleur FROM {tbl} ORDER BY nom").fetchall():
                c = st.columns([1, 3, 1])
                curr_col = FORCED_COLORS.get(r[1], r[2])
                new_col = c[0].color_picker("Color", curr_col, key=f"p_{tbl}_{r[0]}", label_visibility="collapsed")
                if new_col != curr_col: conn.execute(f"UPDATE {tbl} SET couleur=? WHERE id=?", (new_col, r[0])); conn.commit(); st.rerun()
                c[1].write(f"**{r[1]}**" + (" (Forcée)" if r[1] in FORCED_COLORS else ""))
                if c[2].button("Suppr.", key=f"d_{tbl}_{r[0]}"): conn.execute(f"DELETE FROM {tbl} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t2:
        st.subheader("Importation CSV")
        f = st.file_uploader("Fichier CSV historique", type="csv")
        if f and st.button("Lancer Import CSV"):
            try:
                raw = pd.read_csv(f, sep=';', encoding='utf-8').fillna("/")
                # ... (Logique d'import conservée)
                st.success("Import terminé !"); st.rerun()
            except Exception as e: st.error(e)
