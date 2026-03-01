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

VERSION = "1.4"
TODAY = datetime.now().strftime("%d/%m/%Y")

FORCED_COLORS = {
    "JC": "#E22F2F", "Ludo": "#2A33C3", "Nico": "#20DC46",
    "Skydiving Promotion": "#161515", "Sourse": "#C03BD6", "Stemme Belgium": "#999999"
}

def get_connection():
    return sqlite3.connect('gv2_data.db', check_same_thread=False)

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
    collabs = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    clients = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    return pd.concat([collabs, clients]).dropna(subset=['couleur']).set_index('nom')['couleur'].to_dict()

def clean_val(x):
    if pd.isna(x) or x == "/": return 0.0
    s = str(x).replace(',', '.').replace('€', '').strip()
    s = re.sub(r'[^0-9.]', '', s)
    try: return float(s)
    except: return 0.0

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

# --- ONGLET 1 : ENCODAGE ---
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

        if st.button("🔍 Vérifier", use_container_width=True):
            if not d_obj or cli == "" or col == "" or t <= 0:
                st.error("Champs obligatoires manquants.")
            else:
                st.session_state.confirm_data = {"date": d_obj.strftime("%d/%m/%Y"), "collab": col, "client": cli, "description": desc, "mission_ref": ref, "temps": t, "tarif_client": tc, "fact_client": t * tc, "tarif_interne": ti, "fact_interne": t * ti}

    if "confirm_data" in st.session_state:
        d = st.session_state.confirm_data
        st.info(f"Confirmer l'ajout pour {d['client']} ?")
        if st.button("🚀 ENREGISTRER", type="primary", use_container_width=True):
            conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", (d['date'], d['collab'], d['client'], d['description'], d['mission_ref'], d['temps'], d['tarif_client'], d['fact_client'], d['tarif_interne'], d['fact_interne']))
            conn.commit(); st.success("Enregistré !"); del st.session_state.confirm_data; st.rerun()

# --- ONGLET 2 : DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard Analytique")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    cmap = get_color_map()
    if not df.empty:
        st.metric("Total CA HT", f"{df['fact_client'].sum():,.2f} €")
        st.plotly_chart(px.bar(df.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=cmap, title="CA par Client"), use_container_width=True)
    else: st.info("Aucune donnée disponible.")

# --- ONGLET 3 : GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Modification des prestations")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    if not df_edit.empty:
        df_edit.insert(0, '🗑️', False)
        edited = st.data_editor(df_edit, disabled=["id"], hide_index=True)
        if st.button("💾 Appliquer les modifications"):
            for _, r in edited[edited['🗑️'] == False].iterrows():
                conn.execute("UPDATE prestations SET date=?, collab=?, client=?, description=?, temps=? WHERE id=?", (r['date'], r['collab'], r['client'], r['description'], r['temps'], r['id']))
            conn.commit(); st.success("Mis à jour !"); st.rerun()
        
        to_del = edited[edited['🗑️'] == True]
        if not to_del.empty and st.button("🔥 Supprimer la sélection"):
            confirm_delete_dialog(to_del['id'].tolist())

# --- ONGLET 4 : PARAMÈTRES (RESTAURÉ) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration & Sauvegarde")
    conn = get_connection()
    
    # --- SECTION SAUVEGARDE DB ---
    with st.container(border=True):
        st.subheader("💾 Sauvegarde de sécurité (.db)")
        if os.path.exists("gv2_data.db"):
            with open("gv2_data.db", "rb") as f:
                st.download_button("📥 Télécharger la base de données complète", f, f"backup_gv2_{datetime.now().strftime('%Y%m%d')}.db", "application/x-sqlite3", use_container_width=True)

    t1, t2 = st.tabs(["👥 Listes & Couleurs", "📥 Import CSV"])
    
    with t1:
        # Ajout Collab/Client
        c_col, c_cli = st.columns(2)
        with c_col:
            with st.form("add_collab", clear_on_submit=True):
                n_co = st.text_input("Nouveau Collaborateur")
                if st.form_submit_button("Ajouter"):
                    if n_co: conn.execute("INSERT INTO collaborateurs (nom, couleur) VALUES (?,?)", (n_co.strip(), "#3498db")); conn.commit(); st.rerun()
        with c_cli:
            with st.form("add_client", clear_on_submit=True):
                n_cl = st.text_input("Nouveau Client")
                if st.form_submit_button("Ajouter"):
                    if n_cl: conn.execute("INSERT INTO clients (nom, tarif_defaut, couleur) VALUES (?,?,?)", (n_cl.strip(), 80.0, "#e67e22")); conn.commit(); st.rerun()
        
        st.divider()
        # Gestion Couleurs et Suppression
        for title, table in [("Collaborateurs", "collaborateurs"), ("Clients", "clients")]:
            st.subheader(title)
            data = conn.execute(f"SELECT id, nom, couleur FROM {table} ORDER BY nom").fetchall()
            for r in data:
                cols = st.columns([1, 3, 1])
                new_c = cols[0].color_picker("Color", r[2], key=f"cp_{table}_{r[0]}", label_visibility="collapsed")
                if new_c != r[2]: conn.execute(f"UPDATE {table} SET couleur=? WHERE id=?", (new_c, r[0])); conn.commit(); st.rerun()
                cols[1].write(r[1])
                if cols[2].button("Suppr.", key=f"del_{table}_{r[0]}"):
                    conn.execute(f"DELETE FROM {table} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t2:
        st.subheader("Importation Historique")
        file = st.file_uploader("Choisir un fichier CSV (Séparateur ;)", type="csv")
        if file and st.button("🚀 Lancer l'importation"):
            try:
                df_raw = pd.read_csv(file, sep=';', encoding='utf-8').fillna("/")
                for p in df_raw['collab'].unique():
                    if p != "/": conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (str(p), "#cccccc"))
                for c in df_raw['Nom du client'].unique():
                    if c != "/": conn.execute("INSERT OR IGNORE INTO clients (nom, tarif_defaut, couleur) VALUES (?,?,?)", (str(c), 80.0, "#999999"))
                
                mapping = {'Date':'date', 'collab':'collab', 'Nom du client':'client', 'Description':'description', 'Temps de travail':'temps', 'Facturation horaire client':'fact_client', 'Facturation interne GV2':'fact_interne'}
                df_f = df_raw.rename(columns=mapping)
                df_f['date'] = df_f['date'].apply(lambda d: pd.to_datetime(d, dayfirst=True).strftime("%d/%m/%Y") if d != "/" else "/")
                for c_num in ['temps', 'fact_client', 'fact_interne']:
                    if c_num in df_f.columns: df_f[c_num] = df_f[c_num].apply(clean_val)
                
                cols_ok = ['date', 'collab', 'client', 'description', 'temps', 'fact_client', 'fact_interne']
                df_f[[c for c in cols_ok if c in df_f.columns]].to_sql('prestations', conn, if_exists='append', index=False)
                conn.commit(); st.success("✅ Importation terminée avec succès !"); st.rerun()
            except Exception as e: st.error(f"Erreur : {e}")
