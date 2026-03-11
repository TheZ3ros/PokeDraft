import customtkinter as ctk
from PIL import Image, ImageTk
import requests
import random
import io
import threading
import concurrent.futures
import os

# --- CONFIGURAZIONE ESTETICA ---
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

BG_COLOR = "#F0F2F5"
CARD_BG = "#FFFFFF"
DRAFT_HIGHLIGHT = "#FFCC00"
EMPTY_SLOT_COLOR = "#E0E0E0"

# Palette Colori
TYPE_COLORS = {
    "normal": "#A8A77A", "fire": "#EE8130", "water": "#6390F0", "electric": "#F7D02C",
    "grass": "#7AC74C", "ice": "#96D9D6", "fighting": "#C22E28", "poison": "#A33EA1",
    "ground": "#E2BF65", "flying": "#A98FF3", "psychic": "#F95587", "bug": "#A6B91A",
    "rock": "#B6A136", "ghost": "#735797", "dragon": "#6F35FC", "steel": "#B7B7CE",
    "dark": "#705746", "fairy": "#D685AD"
}

CAT_COLORS = { "physical": "#C92112", "special": "#4F5870", "status": "#8C888C" }

STAT_COLORS = {
    "hp": "#4CAF50", "attack": "#F44336", "defense": "#2196F3",
    "special-attack": "#9C27B0", "special-defense": "#E91E63", "speed": "#FF9800"
}
STAT_LABELS = {"hp":"PS", "attack":"Atk", "defense":"Dif", "special-attack":"SpA", "special-defense":"SpD", "speed":"Vel"}
STAT_KEYS = list(STAT_LABELS.keys())

# --- DATI E LOGICA ---
LIMITI_ID_STIMATI = {
    1: {"pokemon": 151, "moves": 165}, 2: {"pokemon": 251, "moves": 251},
    3: {"pokemon": 386, "moves": 354}, 4: {"pokemon": 493, "moves": 467},
    5: {"pokemon": 649, "moves": 559}, 6: {"pokemon": 721, "moves": 621},
}

DB_STRUMENTI_UTILI = {
    "Leftovers": 2, "Choice Band": 3, "Choice Scarf": 4, "Choice Specs": 4, "Life Orb": 4, 
    "Focus Sash": 4, "Sitrus Berry": 3, "Lum Berry": 3, "Quick Claw": 2, "Expert Belt": 4, 
    "Black Sludge": 4, "Toxic Orb": 4, "Flame Orb": 4, "White Herb": 3, "Power Herb": 4, 
    "Salac Berry": 3, "Assault Vest": 6, "Rocky Helmet": 5, "Eviolite": 5
}

GEN_TO_VERSION_GROUPS = {
    1: ["red-blue", "yellow"], 2: ["gold-silver", "crystal"],
    3: ["ruby-sapphire", "emerald", "firered-leafgreen", "colosseum", "xd"],
    4: ["diamond-pearl", "platinum", "heartgold-soulsilver"],
    5: ["black-white", "black-2-white-2"], 6: ["x-y", "omega-ruby-alpha-sapphire"]
}

DB_NATURE = [
    {"name": "Ardita", "en": "Hardy", "up": None, "down": None},
    {"name": "Schiva", "en": "Lonely", "up": "attack", "down": "defense"},
    {"name": "Audace", "en": "Brave", "up": "attack", "down": "speed"},
    {"name": "Decisa", "en": "Adamant", "up": "attack", "down": "special-attack"},
    {"name": "Birbona", "en": "Naughty", "up": "attack", "down": "special-defense"},
    {"name": "Sicura", "en": "Bold", "up": "defense", "down": "attack"},
    {"name": "Docile", "en": "Docile", "up": None, "down": None},
    {"name": "Placida", "en": "Relaxed", "up": "defense", "down": "speed"},
    {"name": "Scaltra", "en": "Impish", "up": "defense", "down": "special-attack"},
    {"name": "Fiacca", "en": "Lax", "up": "defense", "down": "special-defense"},
    {"name": "Timida", "en": "Timid", "up": "speed", "down": "attack"},
    {"name": "Lesta", "en": "Hasty", "up": "speed", "down": "defense"},
    {"name": "Seria", "en": "Serious", "up": None, "down": None},
    {"name": "Allegra", "en": "Jolly", "up": "speed", "down": "special-attack"},
    {"name": "Ingenua", "en": "Naive", "up": "speed", "down": "special-defense"},
    {"name": "Modesta", "en": "Modest", "up": "special-attack", "down": "attack"},
    {"name": "Mite", "en": "Mild", "up": "special-attack", "down": "defense"},
    {"name": "Quieta", "en": "Quiet", "up": "special-attack", "down": "speed"},
    {"name": "Ritrosa", "en": "Bashful", "up": None, "down": None},
    {"name": "Ardente", "en": "Rash", "up": "special-attack", "down": "special-defense"},
    {"name": "Calma", "en": "Calm", "up": "special-defense", "down": "attack"},
    {"name": "Gentile", "en": "Gentle", "up": "special-defense", "down": "defense"},
    {"name": "Vivace", "en": "Sassy", "up": "special-defense", "down": "speed"},
    {"name": "Cauta", "en": "Careful", "up": "special-defense", "down": "special-attack"},
    {"name": "Furba", "en": "Quirky", "up": None, "down": None},
]

class PokemonDraftApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pokémon Draft Arena - Ultimate Edition")
        self.geometry("1400x950")
        self.configure(fg_color=BG_COLOR)
        
        # Stato
        self.gen_max = 4
        self.squadra = []
        self.active_slot_index = 0
        self.draft_step = "POKEMON" 
        self.buffer_scelte = {"pokemon": [], "move": [], "ability": []}
        self.stato_download = {"pokemon": False, "move": False, "ability": False}

        # Modificatori
        self.mod_no_legend = ctk.BooleanVar(value=False)
        self.mod_final_evo = ctk.BooleanVar(value=False)
        self.mod_legal_moves = ctk.BooleanVar(value=False)
        self.mod_legal_abilities = ctk.BooleanVar(value=False)

        # Layout UI
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 1. TOP: Area Draft
        self.frame_draft = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_draft.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        
        self.lbl_title = ctk.CTkLabel(self.frame_draft, text="Configurazione", font=("Arial", 24, "bold"))
        self.lbl_title.pack(pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.frame_draft, width=400)
        
        self.container_opzioni = ctk.CTkFrame(self.frame_draft, fg_color="transparent")
        self.container_opzioni.pack(expand=True, fill="both")

        # 2. BOTTOM: Roster
        self.frame_roster = ctk.CTkFrame(self, fg_color="#FFF8E1", corner_radius=20)
        self.frame_roster.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        
        self.roster_widgets = []
        self.container_roster_cards = ctk.CTkFrame(self.frame_roster, fg_color="transparent")
        self.container_roster_cards.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i in range(6):
            self.squadra.append(None)
            self.roster_widgets.append(self._crea_slot_roster(i))

        self.mostra_configurazione()

    def _crea_slot_roster(self, index):
        f = ctk.CTkFrame(self.container_roster_cards, fg_color="transparent")
        f.pack(side="left", fill="both", expand=True, padx=5)
        border = ctk.CTkFrame(f, fg_color="white", border_width=2, border_color=EMPTY_SLOT_COLOR, corner_radius=15)
        border.pack(fill="both", expand=True)
        ctk.CTkLabel(border, text=str(index+1), font=("Arial", 40, "bold"), text_color="#EEE").place(relx=0.5, rely=0.5, anchor="center")
        return border

    # --- LOGICA FETCHING & UTILS ---
    def _get_en_flavor_text(self, data):
        """Estrae la descrizione in inglese dall'API, pulendola da ritorni a capo."""
        for entry in data.get('flavor_text_entries', []):
            if entry['language']['name'] == 'en':
                return entry['flavor_text'].replace('\n', ' ').replace('\f', ' ')
        return "Nessuna descrizione disponibile."

    def fetch_single_item(self, categoria, max_id):
        try:
            margine = 50 if categoria != "pokemon" else 0
            id_rand = random.randint(1, max_id + margine)
            endpoint = "pokemon-species" if categoria == "pokemon" else categoria
            
            res = requests.get(f"https://pokeapi.co/api/v2/{endpoint}/{id_rand}", timeout=4)
            if res.status_code != 200: return None
            data = res.json()
            
            if 'generation' in data and int(data['generation']['url'].split("/")[-2]) > self.gen_max: return None

            final_data = {"type": categoria, "name": data['name'].replace("-", " ").title(), "real_name": data['name']}
            
            if categoria == "pokemon":
                if self.mod_no_legend.get() and (data.get('is_legendary') or data.get('is_mythical')): return None
                if self.mod_final_evo.get() and not self.is_final_stage(data): return None
                
                pk_res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{id_rand}", timeout=4).json()
                final_data.update({
                    "sprite": pk_res['sprites']['front_default'],
                    "types": [t['type']['name'] for t in pk_res['types']],
                    "stats": {s['stat']['name']: s['base_stat'] for s in pk_res['stats']},
                    "gender_rate": data['gender_rate'],
                    "raw_data": pk_res
                })
            
            elif categoria == "move":
                final_data.update({
                    "element": data['type']['name'],
                    "category": data['damage_class']['name'],
                    "power": data.get('power', 0),
                    "accuracy": data.get('accuracy', 0),
                    "desc": self._get_en_flavor_text(data)
                })
            
            elif categoria == "ability":
                final_data["desc"] = self._get_en_flavor_text(data)

            return final_data
        except: return None

    def worker_download(self, categoria, n_items):
        max_id = LIMITI_ID_STIMATI[self.gen_max].get(categoria, 800)
        if categoria == "pokemon": max_id = LIMITI_ID_STIMATI[self.gen_max]["pokemon"]
        
        validi = []
        nomi = set()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            while len(validi) < n_items:
                futures = [executor.submit(self.fetch_single_item, categoria, max_id) for _ in range(15)]
                for f in concurrent.futures.as_completed(futures):
                    item = f.result()
                    if item and item['real_name'] not in nomi:
                        nomi.add(item['real_name'])
                        validi.append(item)
                        if len(validi) >= n_items: break
        
        self.buffer_scelte[categoria] = [validi[i:i+3] for i in range(0, n_items, 3)]
        self.stato_download[categoria] = True

    def start_pipeline(self):
        def flow():
            self.worker_download("pokemon", 6 * 3)
            if not self.mod_legal_moves.get(): self.worker_download("move", 24 * 3)
            else: self.stato_download["move"] = True
            
            if self.mod_legal_abilities.get() or self.gen_max < 3: self.stato_download["ability"] = True
            else: self.worker_download("ability", 6 * 3)
        threading.Thread(target=flow, daemon=True).start()

    # --- FLUSSO GIOCO ---
    def mostra_configurazione(self):
        for w in self.container_opzioni.winfo_children(): w.destroy()
        
        fr = ctk.CTkFrame(self.container_opzioni, fg_color="white", corner_radius=15)
        fr.pack(pady=20, padx=20, fill="both", expand=True)
        
        ctk.CTkLabel(fr, text="Seleziona Generazione", font=("Arial", 18, "bold")).pack(pady=10)
        fr_gens = ctk.CTkFrame(fr, fg_color="transparent")
        fr_gens.pack()
        for i in range(1, 7):
            ctk.CTkButton(fr_gens, text=f"Gen {i}", width=60, command=lambda g=i: self.avvia_gioco(g)).pack(side="left", padx=5)

        ctk.CTkLabel(fr, text="Modificatori", font=("Arial", 18, "bold")).pack(pady=(20, 10))
        ctk.CTkCheckBox(fr, text="No Leggendari", variable=self.mod_no_legend).pack(pady=5)
        ctk.CTkCheckBox(fr, text="Solo Evoluzione Finale", variable=self.mod_final_evo).pack(pady=5)
        ctk.CTkCheckBox(fr, text="Solo Mosse Legali", variable=self.mod_legal_moves).pack(pady=5)
        ctk.CTkCheckBox(fr, text="Solo Abilità Legali", variable=self.mod_legal_abilities).pack(pady=5)

    def avvia_gioco(self, gen):
        self.gen_max = gen
        self.active_slot_index = 0
        self.draft_step = "POKEMON"
        self._aggiorna_tutto_il_roster()
        self.start_pipeline()
        self.attendi_dati("pokemon", self.mostra_opzioni_draft)

    def attendi_dati(self, categoria, callback):
        if self.stato_download[categoria]:
            self.progress_bar.pack_forget()
            callback()
        else:
            for w in self.container_opzioni.winfo_children(): w.destroy()
            self.progress_bar.pack(pady=20)
            self.progress_bar.start()
            self.lbl_title.configure(text=f"Caricamento {categoria}...")
            self.after(200, lambda: self.attendi_dati(categoria, callback))

    def mostra_opzioni_draft(self):
        pk = self.squadra[self.active_slot_index]
        
        if self.draft_step == "POKEMON":
            opzioni = self.buffer_scelte["pokemon"][self.active_slot_index]
            self.lbl_title.configure(text=f"Scelta Pokémon ({self.active_slot_index+1}/6)")
        
        elif self.draft_step == "MOVES":
            self.lbl_title.configure(text=f"Mossa {len(pk['moves'])+1}/4 per {pk['name']} ({self.active_slot_index+1}/6)")
            idx = (self.active_slot_index * 4) + len(pk['moves'])
            if self.mod_legal_moves.get():
                opzioni = pk['_legal_moves_pool'][len(pk['moves'])] 
            else:
                opzioni = self.buffer_scelte["move"][idx]

        elif self.draft_step == "ABILITY":
            self.lbl_title.configure(text=f"Abilità per {pk['name']} ({self.active_slot_index+1}/6)")
            if self.mod_legal_abilities.get():
                opzioni = self.genera_abilita_legali(pk['raw_data'])
            else:
                opzioni = self.buffer_scelte["ability"][self.active_slot_index]

        elif self.draft_step == "NATURE":
            self.lbl_title.configure(text=f"Natura per {pk['name']} ({self.active_slot_index+1}/6)")
            opzioni = self.genera_nature()

        elif self.draft_step == "EVS":
            self.lbl_title.configure(text=f"EVs per {pk['name']} ({self.active_slot_index+1}/6)")
            opzioni = self.genera_evs()
            
        elif self.draft_step == "ITEM":
            self.lbl_title.configure(text=f"Strumento per {pk['name']} ({self.active_slot_index+1}/6)")
            opzioni = self.genera_strumenti()

        self._render_cards(opzioni)

    # --- RENDERING CARDS ---
    def _render_cards(self, opzioni):
        for w in self.container_opzioni.winfo_children(): w.destroy()
        
        for op in opzioni:
            card = ctk.CTkFrame(self.container_opzioni, width=280, height=360, fg_color="white", corner_radius=15, border_width=1, border_color="#CCC")
            card.pack(side="left", padx=15, pady=10, fill="y", expand=True)
            card.pack_propagate(False)

            if self.draft_step == "POKEMON":
                header = ctk.CTkFrame(card, height=100, fg_color="#E74C3C", corner_radius=15)
                header.place(relx=0, rely=0, relwidth=1)
                ctk.CTkFrame(card, height=20, fg_color="white", corner_radius=0).place(relx=0, rely=0.28, relwidth=1)
                
                lbl_img = ctk.CTkLabel(card, text="")
                lbl_img.place(relx=0.5, rely=0.25, anchor="center")
                self._load_image(op['sprite'], lbl_img, (120, 120))
                
                ctk.CTkLabel(card, text=op['name'], font=("Arial", 20, "bold"), text_color="black").place(relx=0.5, rely=0.45, anchor="center")
                
                fr_types = ctk.CTkFrame(card, fg_color="transparent")
                fr_types.place(relx=0.5, rely=0.55, anchor="center")
                for t in op['types']:
                    ctk.CTkLabel(fr_types, text=t.upper(), fg_color=TYPE_COLORS.get(t,"#777"), text_color="white", corner_radius=10, width=60).pack(side="left", padx=2)
                
                fr_stats = ctk.CTkFrame(card, fg_color="transparent")
                fr_stats.place(relx=0.5, rely=0.75, anchor="center", relwidth=0.9)
                r, c = 0, 0
                for k in STAT_KEYS:
                    ctk.CTkLabel(fr_stats, text=STAT_LABELS[k], font=("Arial", 10, "bold"), text_color="#555").grid(row=r, column=c*2, sticky="e", padx=2)
                    pb = ctk.CTkProgressBar(fr_stats, width=50, height=6, progress_color=STAT_COLORS[k])
                    pb.set(op['stats'][k]/200)
                    pb.grid(row=r, column=c*2+1, sticky="w")
                    r += 1
                    if r > 2: r=0; c+=1

            elif self.draft_step == "MOVES":
                col = TYPE_COLORS.get(op['element'], "#777")
                card.configure(border_color=col, border_width=2)
                ctk.CTkLabel(card, text=op['name'].upper(), font=("Arial", 18, "bold"), text_color=col).pack(pady=(20, 5))
                fr = ctk.CTkFrame(card, fg_color="transparent")
                fr.pack(pady=5)
                ctk.CTkLabel(fr, text=op['element'].upper(), fg_color=col, text_color="white", corner_radius=10, width=70).pack(side="left", padx=2)
                ctk.CTkLabel(fr, text=op['category'].upper(), fg_color=CAT_COLORS.get(op['category'], "#777"), text_color="white", corner_radius=10, width=70).pack(side="left", padx=2)
                ctk.CTkLabel(card, text=f"POT: {op['power'] or '-'}  PREC: {op['accuracy'] or '-'}", font=("Arial", 12, "bold"), text_color="gray").pack(pady=10)
                ctk.CTkLabel(card, text=op['desc'], font=("Arial", 11), text_color="#333", wraplength=240).pack(pady=10)

            elif self.draft_step == "ITEM":
                lbl = ctk.CTkLabel(card, text="")
                lbl.pack(pady=(30, 10))
                self._load_image(op['sprite'], lbl, (80, 80))
                ctk.CTkLabel(card, text=op['name'], font=("Arial", 18, "bold"), text_color="black").pack()
                ctk.CTkLabel(card, text=op['desc'], font=("Arial", 11), text_color="#555", wraplength=240).pack(pady=10)

            elif self.draft_step == "NATURE":
                ctk.CTkLabel(card, text=op['name'].upper(), font=("Arial", 22, "bold"), text_color="black").pack(pady=(50, 20))
                if op['up']:
                    ctk.CTkLabel(card, text=f"{STAT_LABELS[op['up']]} ▲", fg_color="#C8E6C9", text_color="#2E7D32", corner_radius=5, width=120, height=30).pack(pady=5)
                    ctk.CTkLabel(card, text=f"{STAT_LABELS[op['down']]} ▼", fg_color="#FFCDD2", text_color="#C62828", corner_radius=5, width=120, height=30).pack(pady=5)
                else:
                    ctk.CTkLabel(card, text="Neutre", text_color="gray").pack()

            elif self.draft_step == "EVS":
                ctk.CTkLabel(card, text="TOTALE: 510", font=("Arial", 16, "bold"), text_color="gray").pack(pady=20)
                fr = ctk.CTkFrame(card, fg_color="transparent")
                fr.pack(fill="x", padx=20)
                for k in STAT_KEYS:
                    row = ctk.CTkFrame(fr, fg_color="transparent")
                    row.pack(fill="x", pady=3)
                    ctk.CTkLabel(row, text=STAT_LABELS[k], width=30, font=("Arial", 11, "bold")).pack(side="left")
                    p = ctk.CTkProgressBar(row, progress_color=STAT_COLORS[k], height=8)
                    p.set(op['values'][k]/252) 
                    p.pack(side="left", padx=5, fill="x", expand=True)
                    # Qui mettiamo il valore numerico in evidenza
                    ctk.CTkLabel(row, text=str(op['values'][k]), font=("Arial", 11, "bold"), width=30).pack(side="right")
            
            else:
                ctk.CTkLabel(card, text=op['name'].upper(), font=("Arial", 18, "bold"), text_color="black").pack(pady=40)
                if 'desc' in op: ctk.CTkLabel(card, text=op['desc'], wraplength=240).pack()

            ctk.CTkButton(card, text="Seleziona", fg_color=DRAFT_HIGHLIGHT, text_color="black", hover_color="#FFD700", 
                          command=lambda o=op: self.conferma_scelta(o)).place(relx=0.5, rely=0.9, anchor="center", relwidth=0.8)

    # --- FUNZIONE LOGICA DI AVANZAMENTO STATO ---
    def _avanza_stato(self):
        fasi = ["POKEMON", "MOVES"]
        if self.gen_max >= 3: fasi.append("ABILITY")
        fasi.extend(["NATURE", "EVS"])
        if self.gen_max >= 2: fasi.append("ITEM")

        self.active_slot_index += 1
        
        if self.active_slot_index >= 6:
            self.active_slot_index = 0
            idx_fase_attuale = fasi.index(self.draft_step)
            
            if idx_fase_attuale + 1 < len(fasi):
                self.draft_step = fasi[idx_fase_attuale + 1]
            else:
                self.draft_step = "DONE"
                self.fine_draft()

    def conferma_scelta(self, op):
        pk = self.squadra[self.active_slot_index]
        old_index = self.active_slot_index  
        
        if self.draft_step == "POKEMON":
            rate = op.get('gender_rate', -1); sesso = "N/A"
            if rate == 0: sesso = "M"; 
            elif rate == 8: sesso = "F"
            elif rate != -1: sesso = random.choice(["M", "F"])
            
            self.squadra[self.active_slot_index] = {
                "name": op['name'], "real_name": op['real_name'], "sprite": op['sprite'], "types": op['types'],
                "stats": op['stats'], "raw_data": op['raw_data'], "sesso": sesso,
                "moves": [], "ability": None, "item": None, "nature": None, "evs": None
            }
            if self.mod_legal_moves.get():
                self.squadra[self.active_slot_index]['_legal_moves_pool'] = self.genera_mosse_legali(op['raw_data'])
            
            self._avanza_stato()

        elif self.draft_step == "MOVES":
            pk['moves'].append(op)
            if len(pk['moves']) >= 4:
                self._avanza_stato()
        
        elif self.draft_step == "ABILITY": 
            pk['ability'] = op['name']
            self._avanza_stato()
            
        elif self.draft_step == "NATURE": 
            pk['nature'] = op
            self._avanza_stato()
            
        elif self.draft_step == "EVS": 
            pk['evs'] = op['values']
            self._avanza_stato()
            
        elif self.draft_step == "ITEM": 
            pk['item'] = op
            self._avanza_stato()

        new_index = self.active_slot_index
        
        self._aggiorna_slot_roster(old_index)
        if old_index != new_index:
            self._aggiorna_slot_roster(new_index)
        
        if self.draft_step != "DONE":
            self.mostra_opzioni_draft()

    # --- RENDERING ROSTER ---
    def _aggiorna_tutto_il_roster(self):
        for i in range(6):
            self._aggiorna_slot_roster(i)

    def _aggiorna_slot_roster(self, index):
        widget = self.roster_widgets[index]
        for w in widget.winfo_children(): w.destroy()
        
        pk = self.squadra[index]
        border_col = DRAFT_HIGHLIGHT if index == self.active_slot_index else ("#2196F3" if pk and pk['evs'] else EMPTY_SLOT_COLOR)
        bg = "white" if pk else "transparent"
        
        inner = ctk.CTkFrame(widget, fg_color=bg, corner_radius=15, border_width=2, border_color=border_col)
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        
        if not pk:
            ctk.CTkLabel(inner, text=str(index+1), font=("Arial", 40, "bold"), text_color="#EEE").place(relx=0.5, rely=0.5, anchor="center")
            return
            
        lbl_img = ctk.CTkLabel(inner, text="")
        lbl_img.pack(pady=(5,0))
        self._load_image(pk['sprite'], lbl_img, (90, 90))
        
        sex = f" {pk['sesso']}" if pk['sesso'] != "N/A" else ""
        ctk.CTkLabel(inner, text=f"{pk['name']}{sex}", font=("Arial", 12, "bold"), text_color="black").pack()
        
        fr_types = ctk.CTkFrame(inner, fg_color="transparent", height=20)
        fr_types.pack(pady=2)
        for t in pk['types']:
            ctk.CTkLabel(fr_types, text=t.upper(), fg_color=TYPE_COLORS.get(t,"#777"), text_color="white", corner_radius=6, font=("Arial", 8, "bold"), width=40).pack(side="left", padx=1)

        ab_text = pk['ability'] if pk['ability'] else "..."
        ctk.CTkLabel(inner, text=ab_text, fg_color="#F0F0F0", text_color="#333", corner_radius=8, font=("Arial", 10)).pack(pady=2, padx=10, fill="x")

        fr_item = ctk.CTkFrame(inner, fg_color="transparent")
        fr_item.pack(pady=1)
        if pk['item']:
            icon = ctk.CTkLabel(fr_item, text="", width=20); icon.pack(side="left")
            self._load_image(pk['item']['sprite'], icon, (20, 20))
            ctk.CTkLabel(fr_item, text=pk['item']['name'], font=("Arial", 10), text_color="#444").pack(side="left")
        else:
            ctk.CTkLabel(fr_item, text="...", text_color="#CCC").pack()

        fr_moves = ctk.CTkFrame(inner, fg_color="transparent")
        fr_moves.pack(pady=2, fill="x", padx=5)
        for m_idx in range(4):
            if m_idx < len(pk['moves']):
                m = pk['moves'][m_idx]
                col = TYPE_COLORS.get(m['element'], "#777")
                ctk.CTkLabel(fr_moves, text=m['name'], fg_color=col, text_color="white", corner_radius=4, font=("Arial", 9), height=18).pack(fill="x", pady=1)
            else:
                ctk.CTkFrame(fr_moves, fg_color="#F5F5F5", height=18, corner_radius=4).pack(fill="x", pady=1)

        nat_text = f"{pk['nature']['name']} (+{STAT_LABELS.get(pk['nature']['up'],'')} -{STAT_LABELS.get(pk['nature']['down'],'')})" if pk['nature'] else "Natura..."
        ctk.CTkLabel(inner, text=nat_text, font=("Arial", 9), text_color="gray").pack()

        # --- MODIFICA EVS NEL ROSTER ---
        # Aggiunto fill="both" e expand=True per spingere le EV verso il basso e occupare spazio
        fr_evs = ctk.CTkFrame(inner, fg_color="transparent")
        fr_evs.pack(fill="both", expand=True, padx=10, pady=5)
        if pk['evs']:
            for k in STAT_KEYS:
                if pk['evs'][k] > 0:
                    r = ctk.CTkFrame(fr_evs, fg_color="transparent")
                    r.pack(fill="x", pady=2) # Pady aumentato per distanziare le barre
                    
                    # Nome statistica
                    ctk.CTkLabel(r, text=STAT_LABELS[k], font=("Arial", 9, "bold"), width=25, anchor="w").pack(side="left")
                    
                    # Barra ingrandita e colorata
                    pb = ctk.CTkProgressBar(r, progress_color=STAT_COLORS[k], height=6)
                    pb.pack(side="left", fill="x", expand=True, padx=4)
                    pb.set(pk['evs'][k] / 252.0)
                    
                    # Valore numerico della statistica
                    ctk.CTkLabel(r, text=str(pk['evs'][k]), font=("Arial", 9, "bold"), width=25, anchor="e").pack(side="right")
        else:
            ctk.CTkLabel(fr_evs, text="EVs...", text_color="#CCC", font=("Arial", 8)).pack(side="bottom")

    # --- GENERATORI LOCALI MULTITHREAD ---
    def genera_nature(self):
        return random.sample(DB_NATURE, 3)

    def genera_evs(self):
        opzioni = []
        for _ in range(3):
            evs = {k: 0 for k in STAT_KEYS}
            rem = 510
            while rem > 0:
                k = random.choice(STAT_KEYS)
                if evs[k] >= 252: continue
                add = random.randint(1, 40) * 2
                if evs[k] + add > 252: add = 252 - evs[k]
                if add > rem: add = rem
                evs[k] += add; rem -= add
            opzioni.append({"type":"evs", "values": evs})
        return opzioni

    def genera_strumenti(self):
        possibili = [k for k,v in DB_STRUMENTI_UTILI.items() if v <= self.gen_max]
        if not possibili: possibili = ["Berry"]
        scelte = random.sample(possibili, 3)
        opzioni = []
        
        # Uso il multithreading per velocizzare la lettura degli strumenti!
        def fetch_item(s):
            try:
                res = requests.get(f"https://pokeapi.co/api/v2/item/{s.lower().replace(' ','-')}", timeout=3).json()
                desc = self._get_en_flavor_text(res)
            except:
                desc = "Strumento utile."
            return {"type": "item", "name": s, "desc": desc, "sprite": f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/{s.lower().replace(' ','-')}.png"}
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            opzioni = list(executor.map(fetch_item, scelte))
            
        return opzioni

    def genera_abilita_legali(self, raw):
        # Multithreading per le abilità
        def fetch_ability(a):
            try:
                res = requests.get(a['ability']['url'], timeout=3).json()
                desc = self._get_en_flavor_text(res)
            except:
                desc = "Nessuna descrizione disponibile."
            return {"type": "ability", "name": a['ability']['name'].replace("-"," ").title(), "real_name": a['ability']['name'], "desc": desc}
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            opzioni = list(executor.map(fetch_ability, raw['abilities']))
            
        return opzioni

    def genera_mosse_legali(self, raw):
        valid_versions = []
        for g in range(1, self.gen_max+1): valid_versions.extend(GEN_TO_VERSION_GROUPS[g])
        pool = set()
        for m in raw['moves']:
            for v in m['version_group_details']:
                if v['version_group']['name'] in valid_versions:
                    pool.add(m['move']['name'])
                    break
        pool = list(pool)
        if not pool: pool = ["struggle"]
        
        scelte = random.sample(pool, min(12, len(pool)))
        while len(scelte) < 12: scelte.append(random.choice(pool))
        
        # Questa era la parte lenta! Ora scarichiamo tutte le 12 mosse in parallelo
        def fetch_move(m_name):
            try:
                res = requests.get(f"https://pokeapi.co/api/v2/move/{m_name}", timeout=3).json()
                return {
                    "type": "move", "name": res['name'].replace("-", " ").title(), "real_name": res['name'],
                    "element": res['type']['name'], "category": res['damage_class']['name'],
                    "power": res.get('power', 0), "accuracy": res.get('accuracy', 0), 
                    "desc": self._get_en_flavor_text(res)
                }
            except:
                return {"type": "move", "name": m_name.title(), "real_name": m_name, "element": "normal", "category": "status", "power": 0, "accuracy": 0, "desc": "Nessuna info."}
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(fetch_move, scelte))
        
        triplette = []
        for i in range(0, 12, 3):
            triplette.append(results[i:i+3])
        return triplette

    # --- EXPORT ---
    def fine_draft(self):
        self.lbl_title.configure(text="SQUADRA COMPLETA!")
        for w in self.container_opzioni.winfo_children(): w.destroy()
        ctk.CTkButton(self.container_opzioni, text="SALVA TEAM SHOWDOWN", width=300, height=80, fg_color="#4CAF50",
                      font=("Arial", 20, "bold"), command=self.salva_file).pack(pady=50)

    def salva_file(self):
        txt = ""
        SHOWDOWN_EV_LABELS = {"hp":"HP", "attack":"Atk", "defense":"Def", "special-attack":"SpA", "special-defense":"SpD", "speed":"Spe"}
        
        for p in self.squadra:
            gender_str = f" ({p['sesso']})" if p['sesso'] in ["M", "F"] else ""
            item_str = f" @ {p['item']['name']}" if p['item'] else ""
            txt += f"{p['name']}{gender_str}{item_str}\n"
            
            if p['ability']: 
                txt += f"Ability: {p['ability']}\n"
            
            if p['evs']:
                ev_l = [f"{p['evs'][k]} {SHOWDOWN_EV_LABELS[k]}" for k in STAT_KEYS if p['evs'][k]>0]
                if ev_l: txt += f"EVs: {' / '.join(ev_l)}\n"
            
            if p['nature']: 
                txt += f"{p['nature']['en']} Nature\n"
                
            txt += "IVs: 31 HP / 31 Atk / 31 Def / 31 SpA / 31 SpD / 31 Spe\n"
            for m in p['moves']: 
                txt += f"- {m['name']}\n"
            txt += "\n"
        
        with open("team_showdown.txt", "w", encoding="utf-8") as f: f.write(txt)
        os.system("start team_showdown.txt")

    # --- UTILS ---
    def _load_image(self, url, label, size):
        def _t():
            try:
                if not url: return
                r = requests.get(url, stream=True)
                if r.status_code==200:
                    i = Image.open(io.BytesIO(r.content)).resize(size, Image.Resampling.NEAREST)
                    label.configure(image=ctk.CTkImage(i, size=size))
            except: pass
        threading.Thread(target=_t, daemon=True).start()

    def is_final_stage(self, species):
        try:
            chain = requests.get(species['evolution_chain']['url']).json()['chain']
            target = species['name']
            def check(n):
                if n['species']['name'] == target: return len(n['evolves_to']) == 0
                for c in n['evolves_to']: 
                    if check(c): return True
                return False
            return check(chain)
        except: return True

if __name__ == "__main__":
    app = PokemonDraftApp()
    app.mainloop()