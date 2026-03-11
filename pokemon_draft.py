import customtkinter as ctk
from PIL import Image, ImageTk
import requests
import random
import io
import threading
import concurrent.futures
import os

# --- CONFIGURAZIONE ESTETICA ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Colori stile "Poké Ball" e Tipi
POKEBALL_RED = "#EE1515" # Rosso acceso per l'intestazione
CARD_BG = "#2B2B2B"      # Grigio scuro per il corpo della card
STAT_BAR_COLOR = "#4CAF50" # Verde per le stats

# Mappa colori ufficiali (o quasi) dei tipi
TYPE_COLORS = {
    "normal": "#A8A77A", "fire": "#EE8130", "water": "#6390F0", "electric": "#F7D02C",
    "grass": "#7AC74C", "ice": "#96D9D6", "fighting": "#C22E28", "poison": "#A33EA1",
    "ground": "#E2BF65", "flying": "#A98FF3", "psychic": "#F95587", "bug": "#A6B91A",
    "rock": "#B6A136", "ghost": "#735797", "dragon": "#6F35FC", "steel": "#B7B7CE",
    "dark": "#705746", "fairy": "#D685AD"
}

# --- CONFIGURAZIONE DATI ---
LIMITI_ID_STIMATI = {
    1: {"pokemon": 151, "moves": 165, "abilities": 0},
    2: {"pokemon": 251, "moves": 251, "abilities": 0},
    3: {"pokemon": 386, "moves": 354, "abilities": 76},
    4: {"pokemon": 493, "moves": 467, "abilities": 123},
    5: {"pokemon": 649, "moves": 559, "abilities": 164},
    6: {"pokemon": 721, "moves": 621, "abilities": 191},
}

DB_STRUMENTI_UTILI = {
    "Leftovers": 2, "Choice Band": 3, "Choice Scarf": 4, "Choice Specs": 4,
    "Life Orb": 4, "Focus Sash": 4, "Sitrus Berry": 3, "Lum Berry": 3,
    "Quick Claw": 2, "Expert Belt": 4, "Black Sludge": 4, "Toxic Orb": 4, 
    "Flame Orb": 4, "White Herb": 3, "Power Herb": 4, "Salac Berry": 3,
    "Assault Vest": 6, "Rocky Helmet": 5, "Eviolite": 5, "Weakness Policy": 6
}

STATISTICHE_LABELS = {"hp": "HP", "attack": "Atk", "defense": "Def", "special-attack": "SpA", "special-defense": "SpD", "speed": "Spe"}
STATISTICHE_KEYS = list(STATISTICHE_LABELS.keys()) # Chiavi API

GEN_TO_VERSION_GROUPS = {
    1: ["red-blue", "yellow"],
    2: ["gold-silver", "crystal"],
    3: ["ruby-sapphire", "emerald", "firered-leafgreen", "colosseum", "xd"],
    4: ["diamond-pearl", "platinum", "heartgold-soulsilver"],
    5: ["black-white", "black-2-white-2"],
    6: ["x-y", "omega-ruby-alpha-sapphire"]
}

class PokemonDraftApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pokémon Draft - Pokédex UI Edition")
        self.geometry("1300x900") # Un po' più larga per le nuove card
        
        self.gen_max = 4
        self.squadra = []
        self.membro_corrente_idx = 0
        self.slot_mossa_corrente = 0
        
        # MODIFICATORI
        self.mod_no_legend = ctk.BooleanVar(value=False)
        self.mod_final_evo = ctk.BooleanVar(value=False)
        self.mod_legal_moves = ctk.BooleanVar(value=False)
        self.mod_legal_abilities = ctk.BooleanVar(value=False)

        self.buffer_scelte = {"pokemon": [], "move": [], "ability": []}
        self.stato_download = {"pokemon": False, "move": False, "ability": False}

        # --- GUI LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="SQUADRA", font=("Arial", 20, "bold")).pack(pady=20)
        
        self.slot_widgets = []
        for i in range(6):
            f = ctk.CTkFrame(self.sidebar, fg_color="transparent", border_color="gray", border_width=1)
            f.pack(fill="x", padx=10, pady=5)
            l = ctk.CTkLabel(f, text=f"Slot {i+1}", anchor="w", justify="left", font=("Arial", 12))
            l.pack(padx=10, pady=5)
            self.slot_widgets.append(l)

        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew")
        
        self.lbl_stato = ctk.CTkLabel(self.main_area, text="", font=("Arial", 24))
        self.lbl_stato.pack(pady=20)
        
        self.progress_bar = ctk.CTkProgressBar(self.main_area, width=400)
        self.cards_container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.cards_container.pack(expand=True, fill="both", padx=20, pady=20)

        self.mostra_selettore_generazione()

    # --- LOGICHE AUSILIARIE (EVs, Evo check) ---
    def genera_spread_ev_random(self):
        stats_short = STATISTICHE_KEYS
        evs = {s: 0 for s in stats_short}
        rimanenti = 510
        while rimanenti > 0:
            stat_scelta = random.choice(stats_short)
            if evs[stat_scelta] >= 252: continue
            pacchetto = random.randint(1, 40) * 2
            if evs[stat_scelta] + pacchetto > 252: pacchetto = 252 - evs[stat_scelta]
            if pacchetto > rimanenti: pacchetto = rimanenti
            evs[stat_scelta] += pacchetto
            rimanenti -= pacchetto
        return evs

    def formatta_testo_ev(self, ev_dict):
        txt = ""
        for s in STATISTICHE_KEYS:
            if ev_dict[s] > 0: txt += f"{STATISTICHE_LABELS[s]}: {ev_dict[s]}\n"
        return txt

    def is_final_stage(self, species_data):
        try:
            res = requests.get(species_data['evolution_chain']['url'], timeout=3)
            chain_data = res.json()['chain']
            target_name = species_data['name']
            def check_node(node):
                if node['species']['name'] == target_name: return len(node['evolves_to']) == 0
                for child in node['evolves_to']:
                    result = check_node(child)
                    if result is not None: return result
                return None
            return check_node(chain_data)
        except: return True

    # --- FETCHING (AGGIORNATO PER TIPI E STATS) ---
    def fetch_single_item(self, categoria, max_id):
        try:
            margine = 50 if categoria != "pokemon" else 0
            id_rand = random.randint(1, max_id + margine)
            endpoint = "pokemon-species" if categoria == "pokemon" else categoria
            
            res = requests.get(f"https://pokeapi.co/api/v2/{endpoint}/{id_rand}", timeout=4)
            if res.status_code != 200: return None
            data = res.json()
            
            if 'generation' in data:
                gen_num = int(data['generation']['url'].strip("/").split("/")[-1])
                if gen_num > self.gen_max: return None 
            
            sprite = None
            gender_rate = -1
            raw_data = None
            types = [] # NUOVO
            stats = {} # NUOVO

            if categoria == "pokemon":
                if self.mod_no_legend.get() and (data.get('is_legendary') or data.get('is_mythical')): return None
                if self.mod_final_evo.get() and not self.is_final_stage(data): return None

                pk_res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{id_rand}", timeout=4)
                if pk_res.status_code != 200: return None
                pk_data = pk_res.json()
                raw_data = pk_data
                sprite = pk_data['sprites']['front_default']
                gender_rate = data['gender_rate']
                
                # Estrazione Tipi (NUOVO)
                types = [t['type']['name'] for t in pk_data['types']]
                
                # Estrazione Stats (NUOVO)
                for s in pk_data['stats']:
                    stats[s['stat']['name']] = s['base_stat']

            return {
                "name": data['name'].replace("-", " ").title(), 
                "real_name": data['name'], 
                "sprite_url": sprite,
                "gender_rate": gender_rate,
                "raw_data": raw_data,
                "types": types, # NUOVO
                "stats": stats  # NUOVO
            }
        except: return None

    def worker_download_categoria(self, categoria, num_triplette):
        max_id = LIMITI_ID_STIMATI[self.gen_max].get(categoria, 800)
        if categoria == "pokemon": max_id = LIMITI_ID_STIMATI[self.gen_max]["pokemon"]
        
        elementi_validi = []
        target = num_triplette * 3
        nomi_presenti = set() 
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            while len(elementi_validi) < target:
                futures = [executor.submit(self.fetch_single_item, categoria, max_id) for _ in range(15)]
                for future in concurrent.futures.as_completed(futures):
                    item = future.result()
                    if item and item['real_name'] not in nomi_presenti:
                        nomi_presenti.add(item['real_name'])
                        elementi_validi.append(item)
                        if len(elementi_validi) >= target: break
        
        triplette = [elementi_validi[i:i+3] for i in range(0, target, 3)]
        self.buffer_scelte[categoria] = triplette
        self.stato_download[categoria] = True

    def avvia_pipeline_download(self):
        def catena():
            self.worker_download_categoria("pokemon", 6)
            if not self.mod_legal_moves.get(): self.worker_download_categoria("move", 24)
            else: self.stato_download["move"] = True
            if self.mod_legal_abilities.get(): self.stato_download["ability"] = True
            elif self.gen_max >= 3: self.worker_download_categoria("ability", 6)
            else: self.stato_download["ability"] = True
        threading.Thread(target=catena, daemon=True).start()

    def attendi_dati_e_procedi(self, categoria, funzione_successiva):
        if self.stato_download[categoria]:
            self.progress_bar.pack_forget()
            self.lbl_stato.configure(text="")
            funzione_successiva()
        else:
            for w in self.cards_container.winfo_children(): w.destroy()
            self.progress_bar.pack(pady=20)
            self.progress_bar.start()
            self.lbl_stato.configure(text=f"Generazione {categoria}...")
            self.after(200, lambda: self.attendi_dati_e_procedi(categoria, funzione_successiva))

    # --- GENERATORI LOCALI ---
    def genera_mosse_legali_per_pokemon(self, pokemon_raw_data):
        versioni_ammesse = []
        for g in range(1, self.gen_max + 1): versioni_ammesse.extend(GEN_TO_VERSION_GROUPS.get(g, []))
        pool_mosse = set()
        for move_entry in pokemon_raw_data['moves']:
            for v_detail in move_entry['version_group_details']:
                if v_detail['version_group']['name'] in versioni_ammesse:
                    pool_mosse.add(move_entry['move']['name']); break
        lista_mosse = list(pool_mosse)
        if not lista_mosse: lista_mosse = ["struggle"]
        mosse_scelte = random.sample(lista_mosse, min(12, len(lista_mosse)))
        while len(mosse_scelte) < 12: mosse_scelte.append(random.choice(lista_mosse))
        triplette = []
        for i in range(0, 12, 3):
            chunk = mosse_scelte[i : i+3]
            triplette.append([{"name": m.replace("-", " ").title(), "real_name": m, "sprite_url": None} for m in chunk])
        return triplette

    def genera_abilita_legali_per_pokemon(self, pokemon_raw_data):
        abilities = [ab['ability']['name'] for ab in pokemon_raw_data['abilities']]
        opzioni = [{"name": a.replace("-", " ").title(), "real_name": a, "sprite_url": None} for a in abilities]
        return [opzioni]

    # --- FLUSSO GIOCO (Invariato) ---
    def mostra_selettore_generazione(self):
        self.lbl_stato.configure(text="Configurazione Partita")
        fr_gen = ctk.CTkFrame(self.cards_container); fr_gen.pack(pady=10)
        ctk.CTkLabel(fr_gen, text="Generazione Massima:").pack()
        for i in range(1, 7): ctk.CTkButton(fr_gen, text=f"Gen {i}", width=60, command=lambda g=i: self.start_game(g)).pack(side="left", padx=5, pady=5)
        fr_mod = ctk.CTkFrame(self.cards_container); fr_mod.pack(pady=20, fill="x", padx=50)
        ctk.CTkLabel(fr_mod, text="Modificatori:").pack(pady=5)
        ctk.CTkCheckBox(fr_mod, text="No Leggendari", variable=self.mod_no_legend).pack(anchor="w", padx=20, pady=5)
        ctk.CTkCheckBox(fr_mod, text="Solo Stadio Finale", variable=self.mod_final_evo).pack(anchor="w", padx=20, pady=5)
        ctk.CTkCheckBox(fr_mod, text="Solo Mosse Possibili", variable=self.mod_legal_moves).pack(anchor="w", padx=20, pady=5)
        ctk.CTkCheckBox(fr_mod, text="Solo Abilità Possibili", variable=self.mod_legal_abilities).pack(anchor="w", padx=20, pady=5)

    def start_game(self, gen):
        self.gen_max = gen; self.squadra = []; self.membro_corrente_idx = 0; self.slot_mossa_corrente = 0
        self.stato_download = {k: False for k in self.stato_download}; self.buffer_scelte = {k: [] for k in self.buffer_scelte}
        for w in self.cards_container.winfo_children(): w.destroy(); self.cards_container.pack_forget()
        self.avvia_pipeline_download(); self.attendi_dati_e_procedi("pokemon", self.inizio_fase_pokemon)

    def inizio_fase_pokemon(self):
        self.progress_bar.pack_forget(); self.cards_container.pack(expand=True, fill="both", padx=20)
        self.mostra_next_pokemon()

    def mostra_next_pokemon(self):
        if self.membro_corrente_idx >= 6:
            self.membro_corrente_idx = 0
            if self.mod_legal_moves.get(): self.inizio_fase_mosse()
            else: self.attendi_dati_e_procedi("move", self.inizio_fase_mosse)
            return
        opzioni = self.buffer_scelte["pokemon"][self.membro_corrente_idx]
        self.lbl_stato.configure(text=f"Scegli Pokémon {self.membro_corrente_idx + 1}/6")
        self._disegna_cards(opzioni, self.seleziona_pokemon, "pokemon") # TIPO POKEMON

    def seleziona_pokemon(self, scelta):
        rate = scelta.get('gender_rate', -1); sesso = "N/A"
        if rate == 0: sesso = "M"
        elif rate == 8: sesso = "F"
        elif rate != -1: sesso = random.choice(["M", "F"])
        self.squadra.append({"name": scelta['name'], "real_name": scelta['real_name'], "sesso": sesso, "mosse": [], "abilita": "", "strumento": "", "evs": {}})
        if self.mod_legal_moves.get(): self.buffer_scelte["move"].extend(self.genera_mosse_legali_per_pokemon(scelta['raw_data']))
        if self.mod_legal_abilities.get(): self.buffer_scelte["ability"].extend(self.genera_abilita_legali_per_pokemon(scelta['raw_data']))
        self.aggiorna_sidebar(); self.membro_corrente_idx += 1; self.mostra_next_pokemon()

    def inizio_fase_mosse(self):
        self.progress_bar.pack_forget(); self.cards_container.pack(expand=True, fill="both", padx=20)
        self.mostra_next_mossa()

    def mostra_next_mossa(self):
        if self.membro_corrente_idx >= 6:
            self.membro_corrente_idx = 0
            if self.mod_legal_abilities.get(): self.inizio_fase_abilita()
            elif self.gen_max >= 3: self.attendi_dati_e_procedi("ability", self.inizio_fase_abilita)
            else: self.inizio_fase_strumenti()
            return
        idx = (self.membro_corrente_idx * 4) + self.slot_mossa_corrente
        if idx >= len(self.buffer_scelte["move"]): pass 
        opzioni = self.buffer_scelte["move"][idx]
        pkmn = self.squadra[self.membro_corrente_idx]['name']
        self.lbl_stato.configure(text=f"Mossa {self.slot_mossa_corrente + 1}/4 per {pkmn}")
        self._disegna_cards(opzioni, self.seleziona_mossa, "testo")

    def seleziona_mossa(self, scelta):
        self.squadra[self.membro_corrente_idx]['mosse'].append(scelta['name'])
        self.aggiorna_sidebar(); self.slot_mossa_corrente += 1
        if self.slot_mossa_corrente >= 4: self.slot_mossa_corrente = 0; self.membro_corrente_idx += 1
        self.mostra_next_mossa()

    def inizio_fase_abilita(self): self.mostra_next_abilita()
    def mostra_next_abilita(self):
        if self.membro_corrente_idx >= 6: self.membro_corrente_idx = 0; self.inizio_fase_strumenti(); return
        opzioni = self.buffer_scelte["ability"][self.membro_corrente_idx]
        pkmn = self.squadra[self.membro_corrente_idx]['name']
        self.lbl_stato.configure(text=f"Abilità per {pkmn}")
        self._disegna_cards(opzioni, self.seleziona_abilita, "testo")

    def seleziona_abilita(self, s):
        self.squadra[self.membro_corrente_idx]['abilita'] = s['name']
        self.aggiorna_sidebar(); self.membro_corrente_idx += 1; self.mostra_next_abilita()

    def inizio_fase_strumenti(self): self.mostra_next_strumento()
    def mostra_next_strumento(self):
        if self.membro_corrente_idx >= 6: self.membro_corrente_idx = 0; self.inizio_fase_evs(); return
        pkmn = self.squadra[self.membro_corrente_idx]['name']
        self.lbl_stato.configure(text=f"Strumento per {pkmn}")
        possibili = [k for k, v in DB_STRUMENTI_UTILI.items() if v <= self.gen_max]
        if not possibili: possibili = ["Nessuno"]
        opzioni = [{"name": s, "sprite_url": None} for s in random.sample(possibili, min(3, len(possibili)))]
        self._disegna_cards(opzioni, self.seleziona_strumento, "testo")

    def seleziona_strumento(self, s):
        self.squadra[self.membro_corrente_idx]['strumento'] = s['name']
        self.aggiorna_sidebar(); self.membro_corrente_idx += 1; self.mostra_next_strumento()

    def inizio_fase_evs(self): self.mostra_next_ev()
    def mostra_next_ev(self):
        if self.membro_corrente_idx >= 6: self.mostra_fine(); return
        pkmn = self.squadra[self.membro_corrente_idx]['name']
        self.lbl_stato.configure(text=f"EVs per {pkmn} (Tot: 510)")
        opzioni = [{"name": self.formatta_testo_ev(s), "dati_reali": s, "sprite_url": None} for s in [self.genera_spread_ev_random() for _ in range(3)]]
        self._disegna_cards(opzioni, self.seleziona_ev, "ev")

    def seleziona_ev(self, s):
        self.squadra[self.membro_corrente_idx]['evs'] = s['dati_reali']
        self.aggiorna_sidebar(); self.membro_corrente_idx += 1; self.mostra_next_ev()

    # ==========================================
    # --- NUOVO SISTEMA DI RENDERING GRAFICO ---
    # ==========================================

    def _disegna_cards(self, opzioni, callback, tipo):
        for w in self.cards_container.winfo_children(): w.destroy()
        
        # Aumentiamo la larghezza delle card per i pokemon per far stare le stats
        card_width = 280 if tipo == "pokemon" else 220
        card_height = 380 if tipo == "pokemon" else 300
        
        for op in opzioni:
            # CARD CONTAINER (Bordo esterno)
            card = ctk.CTkFrame(self.cards_container, width=card_width, height=card_height, corner_radius=20, border_width=2, border_color="#1A1A1A", fg_color=CARD_BG)
            card.pack(side="left", padx=15, pady=15, fill="both", expand=True)
            card.pack_propagate(False) # Impedisce alla card di restringersi

            # --- INTESTAZIONE POKEBALL (Solo per Pokemon e Mosse/Item per coerenza) ---
            header_color = POKEBALL_RED
            header = ctk.CTkFrame(card, height=50, corner_radius=0, fg_color=header_color)
            header.pack(fill="x", side="top")
            
            # Nome nell'intestazione (Bianco, grassetto)
            title_text = op.get('name', 'Opzione')
            if tipo == "ev": title_text = "EV Spread"
            ctk.CTkLabel(header, text=title_text, font=("Arial", 18, "bold"), text_color="white").pack(pady=10)
            
            # Divisore nero stile Pokeball
            ctk.CTkFrame(card, height=5, fg_color="#1A1A1A").pack(fill="x", side="top")

            # --- CORPO DELLA CARD ---
            body = ctk.CTkFrame(card, corner_radius=0, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=10, pady=5)

            # --> LAYOUT SPECIFICO PER POKEMON <--
            if tipo == "pokemon":
                # Immagine
                lbl_img = ctk.CTkLabel(body, text="...", width=120, height=120)
                lbl_img.pack(pady=(10, 5))
                if op.get('sprite_url'):
                     threading.Thread(target=self._load_img_async, args=(op['sprite_url'], lbl_img), daemon=True).start()

                # TIPI (Badges colorati)
                types_frame = ctk.CTkFrame(body, fg_color="transparent")
                types_frame.pack(pady=5)
                for t in op.get('types', []):
                    color = TYPE_COLORS.get(t, "#A8A77A") # Colore tipo o default Normale
                    badge = ctk.CTkFrame(types_frame, fg_color=color, corner_radius=10, height=25)
                    badge.pack(side="left", padx=3)
                    ctk.CTkLabel(badge, text=t.upper(), font=("Arial", 11, "bold"), text_color="white").pack(padx=8, pady=2)
                
                # STATISTICHE BASE (Griglia con barre)
                stats_frame = ctk.CTkFrame(body, fg_color="transparent")
                stats_frame.pack(pady=10, fill="x")
                stats_data = op.get('stats', {})
                
                row = 0
                col = 0
                for stat_key in STATISTICHE_KEYS:
                    val = stats_data.get(stat_key, 0)
                    label_txt = STATISTICHE_LABELS[stat_key]
                    
                    # Etichetta (es. "HP")
                    ctk.CTkLabel(stats_frame, text=label_txt, font=("Arial", 11, "bold"), width=30, anchor="e").grid(row=row, column=col*2, padx=(5,2), pady=2, sticky="e")
                    
                    # Valore e Barra (es. "80 [======]")
                    bar_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
                    bar_frame.grid(row=row, column=col*2 + 1, padx=2, pady=2, sticky="w")
                    
                    ctk.CTkLabel(bar_frame, text=str(val), font=("Arial", 11), width=25, anchor="w").pack(side="left")
                    
                    # Barra di progresso (Max stat base circa 255, normalizziamo a 200 per la barra)
                    progress = min(val / 200.0, 1.0) 
                    bar = ctk.CTkProgressBar(bar_frame, width=60, height=8, progress_color=STAT_BAR_COLOR)
                    bar.set(progress)
                    bar.pack(side="left", padx=2)

                    row += 1
                    if row > 2: # 3 righe, 2 colonne
                        row = 0
                        col += 1

            # --> LAYOUT PER EVS <--
            elif tipo == "ev":
                 ctk.CTkLabel(body, text=op['name'], font=("Consolas", 13), justify="left", anchor="center").pack(pady=20, fill="both", expand=True)

            # --> LAYOUT PER TESTO SEMPLICE (Mosse, Item, Abilità) <--
            else:
                 # Per il testo semplice, usiamo il corpo per centrare bene il contenuto
                 ctk.CTkLabel(body, text=op['name'], font=("Arial", 16), wraplength=180).pack(pady=40, fill="both", expand=True)

            # --- BOTTONE SELEZIONE (Sempre in fondo) ---
            btn = ctk.CTkButton(card, text="SCELGO TE!", fg_color=POKEBALL_RED, hover_color="#CC1212", height=40, font=("Arial", 14, "bold"),
                                command=lambda o=op: callback(o))
            btn.pack(side="bottom", pady=15, padx=20, fill="x")

    def _load_img_async(self, url, label):
        try:
            r = requests.get(url, timeout=2)
            i = Image.open(io.BytesIO(r.content)).resize((120, 120), Image.NEAREST)
            label.configure(image=ctk.CTkImage(i, i, size=(120, 120)), text="")
        except: pass

    def aggiorna_sidebar(self):
        for i, m in enumerate(self.squadra):
            sesso_str = f" ({m['sesso']})" if m.get('sesso') and m['sesso'] != "N/A" else ""
            t = f"{m['name']}{sesso_str}"
            if m['mosse']: t += f"\nMosse: {len(m['mosse'])}"
            if m['abilita']: t += f"\nAbil: {m['abilita']}"
            if m['strumento']: t += f"\nItem: {m['strumento']}"
            if m['evs']: t += "\nEVs: OK"
            self.slot_widgets[i].configure(text=t)

    def mostra_fine(self):
        self.lbl_stato.configure(text="DRAFT COMPLETATO!")
        for w in self.cards_container.winfo_children(): w.destroy()
        ctk.CTkButton(self.cards_container, text="SALVA TEAM (team_showdown.txt)", width=200, height=50, command=self.salva_file).pack(pady=20)

    def salva_file(self):
        txt = ""
        for p in self.squadra:
            item = f" @ {p['strumento']}" if p['strumento'] and p['strumento']!="Nessuno" else ""
            txt += f"{p['name']}{item}\n"
            if p['sesso'] in ["M", "F"]: txt += f"Gender: {p['sesso']}\n"
            if p['abilita'] and p['abilita'] != "Nessuna": txt += f"Ability: {p['abilita']}\n"
            if p['evs']:
                ev_list = [f"{p['evs'][s]} {s}" for s in STATISTICHE_KEYS if p['evs'][s] > 0]
                if ev_list: txt += f"EVs: {' / '.join(ev_list)}\n"
            txt += "IVs: 31 HP / 31 Atk / 31 Def / 31 SpA / 31 SpD / 31 Spe\n"
            for m in p['mosse']: txt += f"- {m}\n"
            txt += "\n"
        with open("team_showdown.txt", "w", encoding="utf-8") as f: f.write(txt)
        os.system("start team_showdown.txt")

if __name__ == "__main__":
    app = PokemonDraftApp()
    app.mainloop()