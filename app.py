import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.0"
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
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()

init_db()

def get_dynamic_colors():
    conn = get_connection()
    c_df = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    l_df = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([c_df, l_df]).set_index('nom')['couleur'].to_dict()
    return {**FORCED_COLORS, **db_colors}

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 1. ENCODAGE (FIXÉ) ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    
    # Chargement des listes
    collabs = pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    
    if not collabs or not clients:
        st.warning("⚠️ Avant d'encoder, vous devez ajouter au moins un Collaborateur et un Client dans l'onglet **⚙️ Paramètres**.")
        if st.button("Aller aux Paramètres"):
            st.info("Cliquez sur l'onglet Paramètres dans le menu à gauche.")
    else:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                d = st.date_input("Date", format="DD/MM/YYYY")
                cli = st.selectbox("Client", [""] + clients)
                col = st.selectbox("Collaborateur", [""] + collabs)
            with c2:
                t = st.number_input("Temps (h)", min_value=0.0, step=0.25)
                tc = st.number_input("Tarif Client (€)", value=80.0)
                ti = st.number_input("Tarif Interne (€)", value=45.0)
            desc = st.text_area("Description")
            ref = st.text_input("Référence Mission")
            
            if st.button("🚀 ENREGISTRER", type="primary", use_container_width=True):
                if cli != "" and col != "" and t > 0:
                    conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                                 (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                    conn.commit()
                    st.success("✅ Prestation enregistrée !")
                    st.balloons()
                else:
                    st.error("Veuillez sélectionner un Client, un Collaborateur et un Temps > 0.")

# --- 2. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        
        sel_m = st.sidebar.multiselect("Filtrer par Mois", sorted(df['Mois_Label'].unique(), reverse=True), default=df['Mois_Label'].unique())
        df_f = df[df['Mois_Label'].isin(sel_m)]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=get_dynamic_colors()), use_container_width=True)
    else: st.info("Aucune donnée à afficher.")

# --- 3. GESTION (MODIFICATION & SUPPRESSION) ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion des prestations")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    
    if not df_edit.empty:
        st.write("Modifiez les cellules directement ou utilisez l'Import/Export pour les gros changements.")
        edited_df = st.data_editor(df_edit, key="editor", num_rows="dynamic", disabled=["id"])
        
        if st.button("💾 Sauvegarder les modifications"):
            try:
                # Cette méthode simplifiée remplace la table par les modifs de l'éditeur
                edited_df.to_sql('prestations', conn, if_exists='replace', index=False)
                st.success("Base de données mise à jour !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la sauvegarde : {e}")
    else:
        st.info("La base de données est vide.")

# --- 4. PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t_maint, t_lists, t_csv = st.tabs(["💾 Maintenance", "👥 Collaborateurs & Clients", "📥 Import CSV"])
    
    with t_maint:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Exporter")
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(f"📥 Backup_{DATE_FILE}.db", f, f"backup_gv2_{DATE_FILE}.db", use_container_width=True)
        with c2:
            st.subheader("Restaurer")
            up_db = st.file_uploader("Fichier .db", type="db")
            if up_db:
                if st.button("🔥 ÉCRASER ET RESTAURER"):
                    with open(DB_PATH, "wb") as f: f.write(up_db.getbuffer())
                    st.success("Restauration réussie !"); st.rerun()

    with t_lists:
        col1, col2 = st.columns(2)
        for i, (title, table) in enumerate([("👥 Collaborateurs", "collaborateurs"), ("🏢 Clients", "clients")]):
            with [col1, col2][i]:
                st.subheader(title)
                with st.form(f"add_{table}", clear_on_submit=True):
                    n = st.text_input(f"Nom")
                    if st.form_submit_button("Ajouter"):
                        if n: conn.execute(f"INSERT OR IGNORE INTO {table} (nom, couleur) VALUES (?,?)", (n.strip(), "#3498db" if i==0 else "#e67e22")); conn.commit(); st.rerun()
                
                for r in conn.execute(f"SELECT id, nom, couleur FROM {table} ORDER BY nom").fetchall():
                    cols = st.columns([3, 1, 1])
                    cols[0].write(r[1])
                    nc = cols[1].color_picker("Couleur", r[2], key=f"cp_{table}_{r[0]}", label_visibility="collapsed")
                    if nc != r[2]: conn.execute(f"UPDATE {table} SET couleur=? WHERE id=?", (nc, r[0])); conn.commit(); st.rerun()
                    if cols[2].button("🗑️", key=f"del_{table}_{r[0]}"): conn.execute(f"DELETE FROM {table} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t_csv:
        st.subheader("📥 Import CSV")
        up_csv = st.file_uploader("Choisir le fichier CSV", type="csv")
        if up_csv:
            df_raw = pd.read_csv(up_csv, sep=';', engine='python')
            mapping = {'date': 'Date', 'collab': 'collab', 'client': 'Nom du client', 'description': 'Description', 'mission_ref': 'Référence de mission', 'temps': 'Temps de travail', 'tarif_client': 'Tarif horaire client', 'fact_client': 'Facturation horaire client', 'tarif_interne': 'Tarif horaire interne GV2', 'fact_interne': 'Facturation interne GV2'}
            found_cols = {v: k for k, v in mapping.items() if v in df_raw.columns}
            df_imp = df_raw[list(found_cols.keys())].rename(columns=found_cols)
            
            # Nettoyage
            if 'date' in df_imp.columns: df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')
            for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                if col in df_imp.columns:
                    df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace(',', '.').str.replace('\xa0', '').str.strip()
                    df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)

            if st.button("✅ Lancer l'importation"):
                cols_db = ['date', 'collab', 'client', 'description', 'mission_ref', 'temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']
                df_final = df_imp[[c for c in cols_db if c in df_imp.columns]]
                df_final.to_sql('prestations', conn, if_exists='append', index=False)
                st.success(f"Importation terminée : {len(df_final)} lignes ajoutées !"); st.balloons()

# --- AIDE ---
elif menu == "ℹ️ Aide & Infos":
    st.header("ℹ️ Aide")
    st.write("1. Configurez vos Clients et Collaborateurs dans **Paramètres**.")
    st.write("2. Encodez vos prestations quotidiennes dans **Encodage**.")
    st.write("3. Analysez vos résultats dans le **Dashboard**.")
    st.write("4. Modifiez ou supprimez des erreurs dans **Gestion**.")
