# DOSSIER TECHNIQUE : ARGON 4
## RÉSOLUTION DU DERNIER KILOMÈTRE (100% DE PERFECTION CADASTRALE ANCFCC)

Ce dossier regroupe l'intégralité des outils, moteurs et spécifications nécessaires à Gemini 4 Argon pour concevoir le solveur cadastral définitif.

### CONTENU DU DOSSIER :

1. **`00_BRIEFING_AND_INSTRUCTIONS/`**
   - `00_PROMPT_POUR_GEMINI_4_ARGON.md` : Le cahier des charges et la commande technique exhaustive à transmettre à Gemini 4 Argon.
   - `SAMPLE_PARCEL_INPUT_REAL.txt` : Coordonnées réelles de terrain (Titre 23085/02, 192 bornes).

2. **`01_PRODUCTION_CLEANER_PIPELINE/`** (Le moteur de nettoyage actuel en production) :
   - `dxf_cleaner_engine.py` : Façade principale d'exécution.
   - `parcel_core.py` : Cœur géométrique (Shapely, boîtes englobantes de textes, détection parcelles et cadres).
   - `sector_riverain_engine.py` : Résolution automatique des riverains depuis le plan de secteur maître.
   - `dxf_cleaner/pipeline.py` : Pipeline séquentiel des 17 étapes de nettoyage.
   - `dxf_cleaner/borne_ops.py` : Repositionnement strict des bornes Bxx.
   - `dxf_cleaner/linear_centering.py` : Centrage des textes sur les voiries et limites linéaires.
   - `dxf_cleaner/geometry_clipping.py` : Découpage propre au cadre ST284.
   - `dxf_cleaner/standards.py` : Standards officiels des calques et styles ANCFCC.

3. **`02_CADASTRE_MASTER_REFERENCE/`** (Les moteurs de génération directe et apprentissage) :
   - `khari9_cadastre_perfect_engine.py` : Moteur de bissectrice extérieure, échelonnement de bornes proches et carroyage 100m.
   - `cadastre_parcel_synthesizer.py` : Parseur universel de texte de bornes vers DXF et KML (calcul de contenance Gauss).
   - `cadastre_rule_miner.py` : Mineur automatique d'invariants spatiaux.
   - `dxf_transformer_engine.py` : Comparateur DXF Avant -> Après pour l'extraction de règles DAO.
   - `CADASTRE_LEARNED_RULES.json` : Coffre de règles spatiales déjà cristallisées.
   - `MASTER_ANCFCC_TEMPLATE.dxf` : Gabarit officiel ANCFCC contenant les 32 blocs réglementaires et 63 calques.
