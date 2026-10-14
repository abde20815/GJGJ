# DOSSIER D'INGÉNIERIE & MASTER PROMPT POUR GEMINI 4 ARGON
## Résolution Définitive du "Dernier Kilomètre" (The Last Mile Problem) : 100% de Perfection dans le Dessin Cadastral Automatisé ANCFCC Maroc

---

## CONTEXTE & MISSION GLOBALE (Pour Gemini 4 Argon)

Tu es sollicité en tant que moteur d'intelligence architecturale et mathématique suprême (**Gemini 4 Argon**) pour concevoir la solution algorithmique définitive à un problème d'automatisation géospatiale de haute précision.

### 1. L'Écosystème Applicatif : "DAHBY PRO SUITE"
L'utilisateur développe et opère une suite logicielle propriétaire de pointe dédiée aux géomètres-topographes et experts fonciers au Maroc :
* **Dahby Pro Suite** : Suite logicielle d'automatisation des livrables cadastraux et topographiques (PyQt, Cython, ezdxf, QGIS).
* **Plugins QGIS Régionaux** : Cadastre Tanger, Oujda, Nador, Fès, Zouagha.
* **App Bornage & Smart Printer VPRO** : Génération des états de parcelles, PV de bornage, fiches ZN2/ST284, et contrôle de conformité RejCAD.
* **Workflow Critique Cible** : **`LAND PARCEL COORDINATE`** (Conversation de référence : `e18f270d-77e5-4064-9893-75bea5779009`).

---

## 2. LA MISSION DU MODULE "LAND PARCEL COORDINATE"

Le module doit prendre en entrée un **texte brut de coordonnées de bornage** fourni directement par le géomètre sur le terrain, et générer de manière 100% autonome, sans **aucun clic manuel dans AutoCAD**, les livrables finaux conformes aux exigences strictes de l'**ANCFCC** (Agence Nationale de la Conservation Foncière, du Cadastre et de la Cartographie).

### A. Données d'Entrée Brutes (Input Exemples Réels) :
```text
23085/02(Ass)
39-46-38-A
R.B du........
T.N
241
B1 820676.46 461180.22
B2 820732.70 461200.42
B3 820744.93 461203.04
...
BP1 824757.74 465825.10
...
B192 820721.05 461172.39
    190618
```
* **En-tête** : Réquisition ou Titre Foncier (`23085/02(Ass)`), Carte topographique/Feuille (`39-46-38-A`), Nature de la propriété (`R.B du...`, `T.N`), Numéro de parcelle (`241` ou `Plle 363`).
* **Série de bornes** : Identifiant ($B_1, B_2, \dots, BP_1, \dots, BPC, BPD$) + Coordonnées métriques Lambert Maroc Zone 1, 2, 3 ou 4 ($X, Y$).
* **Riverains déclarés** : Limites riveraines (ex: "Route goudronnée de 30m", "Chaïbat", "Titre Foncier N° 45892/02", "Propriété dite El Kheir").

### B. Livrables Cibles Exigés (Output Baselines) :
1. **Fichier DXF Cadastral Officiel** basé sur le template maître ANCFCC (`MASTER_ANCFCC_TEMPLATE.dxf` avec 32 blocs officiels et 63 calques standardisés).
2. **Polygone Parcellaire Fermé (`LWPOLYLINE` flag=1)** sur calque `limites` ou `PARCELLE`.
3. **Implantation des Bornes** avec le bloc officiel `borne_plantee` ou `borne_marquee` exactement à chaque vertex.
4. **Habillage des Bornes (Numéros de Bornes)** sur le calque `BRNS`, positionnés à l'extérieur sans aucune collision.
5. **Gestion des Bornes Rapprochées** : Échelonnement dynamique et traits de rappel (`leaders`).
6. **Carroyage Lambert à pas de 100m** : Blocs `CROISI` sur les coordonnées entières ($X \pmod{100} = 0$, $Y \pmod{100} = 0$) avec annotations marginales.
7. **Centroïde & Contenance** : Calcul exact par la formule de Gauss (Shoelace), formaté rigoureusement en `Ha a ca` (Hectares, Ares, Centiares) au centroïde géométrique.
8. **Textes des Riverains** : Parallèles aux segments, orientés selon la règle de lisibilité universelle (sens de lecture normalisé entre $-90^\circ$ et $+90^\circ$).
9. **Export KML Géodésique** : Reprojection en coordonnées WGS84 pour contrôle satellite Google Earth 3D.
10. **Cadre de Mise en Page ST284** : Cadrage automatique aux échelles réglementaires ($1/500, 1/1000, 1/2000, 1/5000$) avec cartouche d'information officiel.

---

## 3. LE NOEUD DU PROBLÈME : POURQUOI L'AUTOMATISATION BUTTE SUR LE "LAST MILE" (90% -> 100%) ?

Actuellement, les générateurs algorithmiques standards et les scripts existants atteignent environ 90% à 95% du résultat, mais requièrent **toujours** l'intervention d'un dessinateur DAO senior dans AutoCAD pour corriger les 5% à 10% restants. Cette intervention humaine détruit le principe d'automatisation totale.

Voici l'inventaire technique exhaustif des goulots d'étranglement qui empêchent d'atteindre le 100% :

### Goulot 1 : Collisions Multi-Entités & Bounding Boxes 2D (Espace Discret vs Continu)
* **Limite du Bissecteur Extérieur Classique** :
  Le vecteur bissecteur extérieur $\vec{b}_{ext}$ fonctionne bien pour un sommet isolé et régulier. Cependant :
  - **Sommets Concaves Aigus (Angles rentrants)** : Le vecteur extérieur pointe parfois vers une autre arête du polygone ou vers un sommet opposé d'une baie étroite, projetant le texte de borne à l'intérieur d'un segment voisin !
  - **Bornes Rapprochées Multiples ($N \ge 3$ bornes à distance $< 2.5m$)** : Le décalage alternatif simple ($1.8m$ puis $3.8m$) échoue si 3 ou 4 bornes se succèdent sur une ligne brisée dense. Les textes ou les traits de rappel se croisent (`intersection de segments`).
  - **Géométrie Réelle des Textes (Bounding Boxes)** : Un texte n'est pas un point géométrique $(x,y)$, c'est un rectangle orienté $W \times H$ déterminé par le nombre de caractères, la police, la justification (`attachment point` ezdxf : `BOTTOM_LEFT`, `MIDDLE_CENTER`, etc.) et la hauteur. Un simple point d'insertion sans collision ne garantit pas que la boîte englobante du texte ne chevauche pas le polygone ou un bloc symbole.

### Goulot 2 : Conflit de Priorité Spatiale Multi-Couches
Sur une planche cadastrale ANCFCC, plusieurs calques concurrents se partagent l'espace restreint du périmètre :
1. Symbole de la borne (`borne_plantee` : rayon $\approx 0.5m$).
2. Nom de la borne (`B142` : texte hauteur 1.8m).
3. Trait de rappel éventuel.
4. Texte de riverain ("Titre Foncier N° 12458/02" : texte longueur 15m à 30m, hauteur 2.0m).
5. Croisillon de carroyage Lambert (`CROISI` : croix de dimension $4m \times 4m$).
6. Valeur numérique de coordonnée du croisillon ($820700$ : hauteur 2.0m).
7. Flèche d'orientation ou détails de voirie (piste, talus, oued).

Quand un croisillon tombe à $1.2m$ d'une borne et que le riverain passe par ce même segment, une superposition catastrophique se produit. Un humain déplace intelligemment le texte du riverain, masque une branche du croisillon ou décale le numéro de borne le long d'une trajectoire sécurisée. L'algorithme basique les dessine tous aveuglément au même endroit.

### Goulot 3 : Topologie Complexe, Enclaves et Segments Courbes
* **Ordre des Bornes et Sens d'Enroulement** :
  Certains géomètres fournissent des listes dans le sens horaire (CW), d'autres trigonométrique (CCW).
* **Parcelles avec Enclaves / Exclaves (Trous intérieurs)** :
  Présence de parcelles exclues au milieu du terrain. L'extérieur géométrique pour le polygone externe est l'inverse pour la frontière de l'enclave !
* **Segments d'Alignement Intermédiaires** :
  Bornes alignées (`BP1`, `BP2`, `BP3` collinéaires sur une clôture ou une route). L'angle au sommet est de $180^\circ$, rendant le calcul de bissectrice classique dégénéré ($\vec{v}_1 + \vec{v}_2 \approx \vec{0}$).

### Goulot 4 : Cadrage Cartographique Dynamique & Échelle Réglementaire (Format ST284)
* La parcelle doit être mise en page dans le format ST284 officiel.
* L'échelle doit obligatoirement être une échelle normalisée ($1/500, 1/1000, 1/2000, 1/5000, 1/10000$).
* Problème d'orientation : Faut-il garder le Nord strict vers le haut (imposé par certaines conservations) ou orienter la parcelle selon son axe principal d'inertie (Oriented Minimum Bounding Box) pour maximiser l'échelle et la lisibilité, avec adjonction d'une rose des vents dynamique ?
* Le centrage automatique de la parcelle dans la fenêtre d'affichage (`VIEWPORT` ou `Layout Paper Space`) sans que les textes périphériques ne soient coupés par le cadre cartouche.

### Goulot 5 : L'Échec de la "Règle Statique Codée en Dur"
Toute tentative de résoudre ce problème par une suite infinie de `if / elif / else` codés à la main échoue inévitablement face à la diversité infinie des formes parcellaires sur le terrain (forme en L, forme en étoile, parcelles étirées de 2km de long sur 10m de large, découpages urbains millimétriques).

---

## 4. LA COMMANDE FORMELLE ADRESSÉE À GEMINI 4 ARGON

En tant que **Gemini 4 Argon**, ton rôle est de formuler une **architecture logicielle et mathématique complète, rigoureuse et implémentable** qui garantit l'éradication totale de ces défauts pour atteindre **100.00% d'autonomie**.

Ton plan d'action doit répondre avec une précision d'orfèvre aux 5 volets fondamentaux suivants :

### VOLET 1 : Formulation Mathématique du Moteur de Placement Anti-Collision
1. Modélise le problème du placement des étiquettes (numéros de bornes, riverains, cotes) non pas comme un offset fixe, mais comme un **Problème d'Optimisation sous Contraintes Spatiales (CSP / Constrained Optimization)** ou un modèle à champs de forces répulsives / recuit simulé (Simulated Annealing) / MILP (Mixed Integer Linear Programming) :
   * Définis la fonction de coût globale $E_{total} = w_1 E_{overlap} + w_2 E_{distance} + w_3 E_{cross} + w_4 E_{readability}$.
   * Définis les pénalités dures (Hard Constraints, $E = \infty$) : intersection avec le contour de la parcelle, superposition texte-texte, croisement de traits de rappel.
   * Définis les pénalités douces (Soft Constraints) : éloignement par rapport à la borne cible, déviation par rapport à la bissectrice naturelle.
2. Détaille l'algorithme exact de calcul de la boîte englobante orientée (OBB - Oriented Bounding Box) pour chaque chaîne de caractères en fonction des paramètres typographiques AutoCAD (hauteur de texte, facteur d'élargissement, justification).
3. Décris l'algorithme de routage des traits de rappel (`leader lines`) pour qu'ils contournent élégamment les obstacles et ne créent jamais d'ambiguïté visuelle sur la borne pointée.

### VOLET 2 : Moteur d'Apprentissage par Différenciation de DXF (DXF Invariant & Rule Mining)
L'utilisateur dispose de paires de fichiers réels :
* **`DXF_AVANT`** : Le fichier brut généré par l'algorithme initial avec ses imperfections.
* **`DXF_APRES`** : Le fichier retouché à la perfection par le géomètre-expert humain dans AutoCAD.
1. Décris l'algorithme exact pour comparer mathématiquement `DXF_AVANT` et `DXF_APRES` :
   * Appariement d'entités (Entity Matching via R-Tree spatial et algorithme de Kuhn-Munkres / Hungarian Algorithm).
   * Calcul du vecteur de déplacement de chaque texte : $\Delta X, \Delta Y, \Delta \theta, \Delta \text{layer}$.
   * Extraction des invariants : identifier pourquoi l'expert a déplacé une étiquette particulière (distance au voisin le plus proche, présence d'un obstacle, orientation de la limite).
2. Propose un format de stockage cristallisé pour ces règles apprises (ex: `CADASTRE_LEARNED_RULES.json`) afin que le moteur s'améliore continuellement sans recompiler le code.

### VOLET 3 : Pipeline d'Ingénierie & Architecture Modulaire (Python / ezdxf / Shapely)
Fournis l'architecture logicielle complète du moteur unifié :
1. **Module 1 : Universal Parser & Topology Sanitizer** :
   * Nettoyage des coordonnées, détection automatique du système de projection Lambert (Zones 1 à 4 Maroc), détection et fermeture des boucles, correction de l'orientation (CCW obligatoire pour la limite externe, CW pour les enclaves), élimination des doublons de sommets avec tolérance centimétrique.
2. **Module 2 : Spatial Layout & Scale Selector** :
   * Calcul de l'enveloppe minimale, sélection déterministe du format de feuille ST284 (A4 à A0) et de l'échelle normalisée officielle ($1/500 \dots 1/5000$) assurant une marge de respiration minimale de 30mm sur papier tout autour de la parcelle.
3. **Module 3 : Carroyage Lambert & Déconfliction des Croisillons** :
   * Génération de la grille $100m$ ou $50m$, filtrage intelligent des croisillons (suppression ou déplacement des croisillons qui intersectent une borne ou un texte critique).
4. **Module 4 : Solver Anti-Collision (The Physics / CSP Engine)** :
   * Implantation des blocs officiels ANCFCC, exécution du solveur spatial pour positionner textes de bornes et riverains avec traits de rappel garantis 0 collision.
5. **Module 5 : Cartouche ST284, Synoptique & Métadonnées** :
   * Remplissage automatique des attributs de cartouche (Numéro de Titre/Réquisition, Contenance exacte en Ha a ca, Date, Échelle, Commune, Province, Spécification du Géomètre).
6. **Module 6 : ANCFCC Pre-Flight Validator & Auto-Healing (Zéro RejCAD)** :
   * Simulateur de validation ANCFCC : vérification de la concordance du centroïde ZN2, conformité des 63 calques, vérification du flag closed=1 des polylignes, absence de superpositions.

### VOLET 4 : Spécifications Précises & Algorithmes Clés en Pseudo-Code / Python
Donne le pseudo-code ou le code Python structuré (typé, modulaire, utilisant `ezdxf`, `shapely`, `scipy.spatial` ou `rtree`) pour :
1. Le calcul de la bissectrice robuste gérant les sommets quasi-collinéaires et rentrants.
2. La détection et résolution de collisions multi-rectangles par séparation d'axes (SAT - Separating Axis Theorem).
3. Le positionnement adaptatif et la segmentation des textes de riverains longs le long des limites parcellaires.

### VOLET 5 : Métriques de Validation & Protocole de Test "Zéro-Défaut"
Définis la batterie de tests d'acceptation automatique :
* Taux de collision résiduel (seuil acceptable = strictement 0.00%).
* Déviation maximale par rapport au dessin de l'expert humain sur les jeux de données de test de Tanger, Oujda, Fès et Nador.
* Temps d'exécution par parcelle (objectif : $< 1.5$ seconde pour une parcelle de 200 bornes).

---

## 5. FORMAT DE RÉPONSE ATTENDU DE GEMINI 4 ARGON
La réponse doit être structurée comme un **Document d'Architecture Technique de Classe Mondiale (World-Class Technical Specification)**, combinant rigueur mathématique, clarté logicielle, diagrammes conceptuels textuels, formules d'optimisation explicites et implémentations de référence prêtes à être intégrées dans le moteur `khari9_cadastre_perfect_engine.py` de l'écosystème DAHBY PRO SUITE.
