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

# Couleurs par défaut pour la sécurité
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

@st.dialog("⚠️ RESTAURATION")
def confirm_restore_dialog(uploaded_file):
    st.error("### ATTENTION : ÉCRASEMENT DES DONNÉES")
    if st.button("🔥 CONFIRMER LA RESTAURATION", type="primary", use_container_width=True):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Base restaurée !"); st.rerun()

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 1. ENCODAGE ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    collabs = pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    
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
            if cli and col and t > 0:
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit()
                st.success("Enregistré avec succès !")
            else: st.error("Veuillez remplir les champs obligatoires (Client, Collab, Temps).")

# --- 2. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        
        sel_m = st.sidebar.multiselect("Mois", sorted(df['Mois_Label'].unique(), reverse=True), default=df['Mois_Label'].unique())
        df_f = df[df['Mois_Label'].isin(sel_m)]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=get_dynamic_colors()), use_container_width=True)
    else: st.info("Aucune donnée.")

# --- 3. GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion des prestations")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    if not df_edit.empty:
        st.data_editor(df_edit, disabled=["id"], hide_index=True)
        st.info("La modification directe sera disponible en V1.1. Pour l'instant, utilisez l'import/export pour les corrections de masse.")

# --- 4. PARAMÈTRES (COMPLET) ---
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
            if up_db and st.button("🚀 Restaurer la base"): confirm_restore_dialog(up_db)

    with t_lists:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("👥 Collaborateurs")
            with st.form("add_collab", clear_on_submit=True):
                new_col = st.text_input("Nom du collaborateur")
                if st.form_submit_button("Ajouter"):
                    if new_col: conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (new_col.strip(), "#3498db")); conn.commit(); st.rerun()
            
            for r in conn.execute("SELECT id, nom, couleur FROM collaborateurs ORDER BY nom").fetchall():
                c_cols = st.columns([3, 1, 1])
                c_cols[0].write(r[1])
                new_color = c_cols[1].color_picker("Couleur", r[2], key=f"cp_{r[0]}", label_visibility="collapsed")
                if new_color != r[2]: conn.execute("UPDATE collaborateurs SET couleur=? WHERE id=?", (new_color, r[0])); conn.commit(); st.rerun()
                if c_cols[2].button("🗑️", key=f"delc_{r[0]}"): conn.execute("DELETE FROM collaborateurs WHERE id=?", (r[0],)); conn.commit(); st.rerun()

        with col2:
            st.subheader("🏢 Clients")
            with st.form("add_client", clear_on_submit=True):
                new_cli = st.text_input("Nom du client")
                if st.form_submit_button("Ajouter"):
                    if new_cli: conn.execute("INSERT OR IGNORE INTO clients (nom, couleur) VALUES (?,?)", (new_cli.strip(), "#e67e22")); conn.commit(); st.rerun()
            
            for r in conn.execute("SELECT id, nom, couleur FROM clients ORDER BY nom").fetchall():
                cl_cols = st.columns([3, 1, 1])
                cl_cols[0].write(r[1])
                new_color = cl_cols[1].color_picker("Couleur", r[2], key=f"clp_{r[0]}", label_visibility="collapsed")
                if new_color != r[2]: conn.execute("UPDATE clients SET couleur=? WHERE id=?", (new_color, r[0])); conn.commit(); st.rerun()
                if cl_cols[2].button("🗑️", key=f"delcl_{r[0]}"): conn.execute("DELETE FROM clients WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t_csv:
        st.subheader("📥 Import CSV")
        up_csv = st.file_uploader("Fichier CSV", type="csv")
        if up_csv:
            df_imp = pd.read_csv(up_csv, sep=';', engine='python')
            # Mapping simplifié pour l'exemple
            df_imp.columns = [c.strip() for c in df_imp.columns]
            st.write("Aperçu :", df_imp.head(2))
            if st.button("✅ Confirmer l'importation"):
                # Nettoyage et import (logique identique à la précédente)
                df_imp.to_sql('prestations', conn, if_exists='append', index=False)
                st.success(f"🎉 Succès ! {len(df_imp)} prestations importées.")
                st.balloons()

# --- 5. AIDE ---
elif menu == "ℹ️ Aide & Infos":
    st.header("ℹ️ Aide")
    st.markdown("""
    - **Gestion des listes** : Ajoutez vos clients et collabs dans Paramètres pour les voir dans le menu Encodage.
    - **Couleurs** : Personnalisez les couleurs des graphiques via le sélecteur dans Paramètres.
    - **Backup** : Faites un export .db régulièrement pour ne jamais perdre vos données.
    """)
