import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import re

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.0"
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

# --- MODALE DE CONFIRMATION (DIALOG) ---
@st.dialog("Confirmer la suppression")
def confirm_delete_dialog(ids_to_delete):
    st.warning(f"⚠️ Êtes-vous sûr de vouloir supprimer définitivement {len(ids_to_delete)} prestation(s) ?")
    st.write("Cette action est irréversible.")
    
    c1, c2 = st.columns(2)
    if c1.button("🔥 Oui, supprimer", type="primary", use_container_width=True):
        conn = get_connection()
        conn.executemany("DELETE FROM prestations WHERE id = ?", [(x,) for x in ids_to_delete])
        conn.commit()
        st.success("Suppressions effectuées.")
        st.rerun()
    
    if c2.button("Annuler", use_container_width=True):
        st.rerun()

# --- NAVIGATION ---
# Ajout du logo en haut de la barre latérale
st.sidebar.image("image_0.png", use_container_width=True)

st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION} | **Date :** {TODAY}")
st.sidebar.divider()

menu = st.sidebar.radio("Navigation", [
    "📝 Encodage", 
    "📊 Dashboard (Analyse)", 
    "🛠️ Gestion des Prestations", 
    "⚙️ Paramètres",
    "ℹ️ Info & Aide"
])

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
            cli = st.selectbox("Client", clients_list, index=0)
            col = st.selectbox("Collaborateur", collabs_list, index=0)
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25, value=0.0)
            tc = st.number_input("Tarif Client (€)", value=80.0)
            ti = st.number_input("Tarif Interne (€)", value=45.0)
        desc = st.text_area("Description / Travail effectué")
        ref = st.text_input("Référence Mission")

        if st.button("🔍 Vérifier la prestation", use_container_width=True):
            if not d_obj or cli == "" or col == "" or t <= 0:
                st.error("⚠️ La date, le client, le collaborateur et le temps sont obligatoires.")
            else:
                st.session_state.confirm_data = {
                    "date": d_obj.strftime("%d/%m/%Y"), "collab": col, "client": cli,
                    "description": desc, "mission_ref": ref, "temps": t,
                    "tarif_client": tc, "fact_client": t * tc, "tarif_interne": ti, "fact_interne": t * ti
                }

    if "confirm_data" in st.session_state:
        st.info("💡 Veuillez confirmer les détails suivants :")
        d = st.session_state.confirm_data
        with st.expander("RÉSUMÉ DE LA SAISIE", expanded=True):
            r1, r2 = st.columns(2)
            r1.write(f"**Date :** {d['date']} | **Collab :** {d['collab']} | **Client :** {d['client']}")
            r2.write(f"**Temps :** {d['temps']}h | **Total Facturé :** {d['fact_client']:.2f}€")
            st.write(f"**Description :** {d['description']}")
        
        cb1, cb2 = st.columns(2)
        if cb1.button("🚀 CONFIRMER & ENREGISTRER", type="primary", use_container_width=True):
            conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (d['date'], d['collab'], d['client'], d['description'], d['mission_ref'], d['temps'], d['tarif_client'], d['fact_client'], d['tarif_interne'], d['fact_interne']))
            conn.commit()
            st.success("✅ Prestation enregistrée !")
            del st.session_state.confirm_data
            st.rerun()
        if cb2.button("❌ Annuler / Modifier", use_container_width=True):
            del st.session_state.confirm_data
            st.rerun()

# --- ONGLET 2 : DASHBOARD ---
elif menu == "📊 Dashboard (Analyse)":
    st.header("📊 Analyse de Performance")
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

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Heures", f"{df_f['temps'].sum():.2f} h")
        k2.metric("Total CA HT", f"{df_f['fact_client'].sum():,.2f} €")
        k3.metric("Marge GV2", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")

        st.subheader("🏢 Analyse par Client")
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=cmap, title="CA par Client (€)", text_auto='.2s'), use_container_width=True)
        c2.plotly_chart(px.bar(df_f.groupby('client')['temps'].sum().reset_index(), x='client', y='temps', color='client', color_discrete_map=cmap, title="Heures par Client (h)", text_auto='.1f'), use_container_width=True)

        st.subheader("👥 Analyse par Collaborateur")
        c3, c4 = st.columns(2)
        c3.plotly_chart(px.bar(df_f.groupby('collab')['fact_client'].sum().reset_index(), x='collab', y='fact_client', color='collab', color_discrete_map=cmap, title="CA par Collab (€)", text_auto='.2s'), use_container_width=True)
        c4.plotly_chart(px.bar(df_f.groupby('collab')['temps'].sum().reset_index(), x='collab', y='temps', color='collab', color_discrete_map=cmap, title="Heures par Collab (h)", text_auto='.1f'), use_container_width=True)

        csv = df_f.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 Exporter la sélection (CSV)", csv, f"export_gv2_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    else:
        st.info("Aucune donnée disponible.")

# --- ONGLET 3 : GESTION DES PRESTATIONS ---
elif menu == "🛠️ Gestion des Prestations":
    st.header("🛠️ Edition des données")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    
    if not df_edit.empty:
        df_edit.insert(0, '🗑️', False)
        edited_df = st.data_editor(df_edit, column_config={"id": None, "🗑️": st.column_config.CheckboxColumn("Suppr?")}, disabled=["id"], use_container_width=True, hide_index=True)
        cs, cd = st.columns(2)
        if cs.button("💾 Sauvegarder les modifications", use_container_width=True):
            for _, r in edited_df[edited_df['🗑️'] == False].iterrows():
                conn.execute("UPDATE prestations SET date=?, collab=?, client=?, description=?, temps=?, fact_client=?, fact_interne=? WHERE id=?", (r['date'], r['collab'], r['client'], r['description'], r['temps'], r['fact_client'], r['fact_interne'], r['id']))
            conn.commit(); st.success("Modifications enregistrées !"); st.rerun()
        to_del = edited_df[edited_df['🗑️'] == True]
        if not to_del.empty and cd.button(f"🔥 SUPPRIMER {len(to_del)} LIGNE(S)", type="primary", use_container_width=True):
            confirm_delete_dialog(to_del['id'].tolist())
    else:
        st.info("Base vide.")

# --- ONGLET 4 : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t1, t2 = st.tabs(["👥 Listes & Couleurs", "📥 Importation CSV"])
    with t1:
        ca, cb = st.columns(2)
        with ca:
            with st.form("f_add_collab", clear_on_submit=True):
                st.subheader("Nouveau Collaborateur")
                n_co = st.text_input("Nom")
                if st.form_submit_button("Ajouter"):
                    if n_co: conn.execute("INSERT INTO collaborateurs (nom, couleur) VALUES (?,?)", (n_co.strip(), "#3498db")); conn.commit(); st.rerun()
        with cb:
            with st.form("f_add_client", clear_on_submit=True):
                st.subheader("Nouveau Client")
                n_cl = st.text_input("Nom")
                if st.form_submit_button("Ajouter"):
                    if n_cl: conn.execute("INSERT INTO clients (nom, tarif_defaut, couleur) VALUES (?,?,?)", (n_cl.strip(), 80.0, "#e67e22")); conn.commit(); st.rerun()
        st.divider()
        for lab, tbl in [("Collaborateurs", "collaborateurs"), ("Clients", "clients")]:
            st.subheader(lab)
            for r in conn.execute(f"SELECT id, nom, couleur FROM {tbl} ORDER BY nom").fetchall():
                c1, c2, c3 = st.columns([1, 4, 2])
                nc = c1.color_picker("C", r[2], key=f"cp_{tbl}_{r[0]}", label_visibility="collapsed")
                if nc != r[2]: conn.execute(f"UPDATE {tbl} SET couleur=? WHERE id=?", (nc, r[0])); conn.commit(); st.rerun()
                c2.write(f"**{r[1]}**")
                dk = f"confirm_del_{tbl}_{r[0]}"
                if c3.button("Supprimer", key=f"btn_del_{dk}"): st.session_state[dk] = True
                if st.session_state.get(dk, False):
                    st.error(f"Supprimer '{r[1]}' ?")
                    y, n = st.columns(2)
                    if y.button("OUI", key=f"y_{dk}", type="primary", use_container_width=True):
                        conn.execute(f"DELETE FROM {tbl} WHERE id=?", (r[0],)); conn.commit(); del st.session_state[dk]; st.rerun()
                    if n.button("NON", key=f"n_{dk}", use_container_width=True): del st.session_state[dk]; st.rerun()
    with t2:
        st.subheader("Importation CSV")
        if "import_msg" in st.session_state:
            st.success(st.session_state.import_msg); del st.session_state.import_msg
        file = st.file_uploader("Choisir un fichier CSV (Séparateur ;)", type="csv")
        if file and st.button("🚀 Lancer l'importation"):
            try:
                df_raw = pd.read_csv(file, sep=';', encoding='utf-8').fillna("/")
                for p in df_raw['collab'].unique():
                    if p != "/": conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (str(p), FORCED_COLORS.get(p, "#cccccc")))
                for c in df_raw['Nom du client'].unique():
                    if c != "/": conn.execute("INSERT OR IGNORE INTO clients (nom, tarif_defaut, couleur) VALUES (?,?,?)", (str(c), 80.0, FORCED_COLORS.get(c, "#999999")))
                mapping = {'Date':'date', 'collab':'collab', 'Nom du client':'client', 'Description':'description', 'Temps de travail':'temps', 'Facturation horaire client':'fact_client', 'Facturation interne GV2':'fact_interne'}
                df_f = df_raw.rename(columns=mapping)
                df_f['date'] = df_f['date'].apply(lambda d: pd.to_datetime(d, dayfirst=True).strftime("%d/%m/%Y") if d != "/" else "/")
                for col_num in ['temps', 'fact_client', 'fact_interne']:
                    if col_num in df_f.columns: df_f[col_num] = df_f[col_num].apply(clean_val)
                cols_final = ['date', 'collab', 'client', 'description', 'temps', 'fact_client', 'fact_interne']
                df_f[[c for c in cols_final if c in df_f.columns]].to_sql('prestations', conn, if_exists='append', index=False)
                conn.commit(); st.session_state.import_msg = f"✅ Importation réussie."; st.rerun()
            except Exception as e: st.error(f"Erreur d'import : {e}")

# --- ONGLET 5 : INFO & AIDE ---
elif menu == "ℹ️ Info & Aide":
    st.header("ℹ️ Informations sur le Système")
    
    st.markdown("""
    Bienvenue dans le système de gestion **GV2 Management**. Cet outil est conçu pour centraliser le suivi des prestations, 
    analyser la rentabilité et simplifier l'encodage collaboratif.
    """)
    
    with st.expander("🚀 Fonctionnalités Principales", expanded=True):
        st.markdown("""
        * **📝 Encodage Sécurisé** : Saisie des prestations avec vérification en deux étapes pour éviter les erreurs. Les champs sont vides par défaut pour forcer une sélection consciente.
        * **📊 Dashboard Analytique** : Visualisation en temps réel du Chiffre d'Affaires et des heures prestées par client et par collaborateur.
        * **🔍 Filtrage Avancé** : Analyse précise par année, mois, client ou collaborateur avec mise à jour instantanée des indicateurs (KPIs).
        * **🛠️ Gestion des Données** : Tableur interactif permettant de modifier ou de supprimer des prestations existantes avec confirmation de sécurité.
        * **⚙️ Paramétrage Personnalisé** : Gestion des listes de clients et collaborateurs avec attribution de couleurs spécifiques pour les graphiques.
        * **📥 Import/Export** : Exportation des données filtrées vers CSV et importation massive de données historiques via fichier Excel/CSV.
        """)
    
    with st.expander("💡 Astuces d'utilisation"):
        st.markdown("""
        1.  **Couleurs** : Changez la couleur d'un client dans 'Paramètres' pour qu'il soit plus reconnaissable dans les graphiques.
        2.  **Export** : Utilisez les filtres du Dashboard avant de cliquer sur 'Exporter' pour n'obtenir que les données nécessaires à votre facturation.
        3.  **Suppression** : En cas d'erreur massive, utilisez la colonne 'Suppr' dans l'onglet 'Gestion' pour traiter plusieurs lignes d'un coup.
        """)
    
    st.divider()
    st.info(f"**GV2 Management System** - Version {VERSION} | Développé pour une gestion agile du temps et du CA.")
