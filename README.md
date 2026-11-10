# Brotato (Python & Pygame-CE Port)

A data-driven, clean-room Python + Pygame-CE implementation of **Brotato** featuring 60+ FPS performance via spatial hashing, exact game mechanics and formulas, Waves 1–20 + Endless Mode, Danger 0–5, 12 distinct characters, 27 weapons (Tiers I–IV), 38 items, weapon class synergies, and drop-in custom asset pack support.

---

## Easy Download & 1-Click Play

### Linux Mint / Ubuntu (Stupid-Easy 1-Command Install)
Paste this single command into **Terminal** — it automatically installs `python3-venv` if missing, downloads the game folder to `~/Games/Brotato-Python`, installs libraries, adds a **Desktop & Mint Games Menu shortcut**, and launches the game:

```bash
curl -fsSL https://raw.githubusercontent.com/ghhygggg58-gif/Brotato/main/install_linux.sh | bash
```

**If your repository is private**, authenticate once with `gh auth login` (or set `GITHUB_TOKEN`) and run:

```bash
gh api repos/ghhygggg58-gif/Brotato/contents/install_linux.sh -H "Accept: application/vnd.github.raw" | bash
```

*(Already downloaded the ZIP? Unzip it, right-click inside the folder → **Open in Terminal**, and run `bash install_linux.sh` or `./play_brotato.sh`.)*

### Option 2: Download ZIP + 1-Click Launcher (Windows / macOS / Linux)
1. Download the game folder from GitHub (**Code → Download ZIP**, or [Direct `main.zip` link](https://github.com/ghhygggg58-gif/Brotato/archive/refs/heads/main.zip)) and unzip it.
2. Run the launcher for your OS (auto-creates `.venv`, installs `pygame-ce` & `numpy` on first launch, and starts the game):
   - **Linux / Mint**: Run **`./play_brotato.sh`** (or **`./play_brotato.sh --install-shortcut`** to add the Desktop & Menu icon)
   - **Windows**: Double-click **`Play_Brotato.bat`**
   - **macOS**: Double-click **`Play_Brotato.command`** (or run `./play_brotato.sh`)

### Option 3: Easy 1-Script Downloader (`download_brotato.py`)
Download just `download_brotato.py` (uses only Python's standard library) and run:

```bash
python3 download_brotato.py --run --shortcut --fix-linux-deps
```

Useful options:
- Save a clean standalone zip only: `python3 download_brotato.py --zip-only`
- Choose output folder: `python3 download_brotato.py --dest ./MyBrotato`
- Private repository support: `GITHUB_TOKEN=... python3 download_brotato.py --run` (or automatically via `gh` CLI if logged in)
- Build a clean distribution zip from a local checkout: `python3 scripts/package_zip.py`

### Option 4: Manual Python Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### CLI Options
```bash
python main.py --width 1280 --height 720 --fps 60
python main.py --headless-smoke
```

---

## Controls

| Action | Input |
| :--- | :--- |
| Move | `WASD` or `Arrow Keys` |
| Aim Mode Toggle (Auto-Aim / Manual Mouse) | `M` (or top-right HUD button) |
| Sound Mute Toggle | `N` |
| Pause / Resume | `ESC` |
| Performance & Entity Debug HUD | `F3` |
| Shop / Level-Up Shortcuts | Mouse click, or `1-4` (upgrades), `R` (reroll), `Enter`/`Space` (Go!) |

---

## Implemented Systems & Exact Mechanics

- **Full 20-Wave Run + Endless Mode + Danger 0–5**:
  - Escalating wave timers (20s Wave 1 up to 60s Waves 11–19, 90s Boss Wave 20), Horde/Swarm waves, Rare Loot Aliens, Elite mini-bosses, and Wave 20 Bosses (*The Predator* & *The Watcher*, with Double Boss on Danger 5).
  - Endless Mode continuation after clearing Wave 20.
  - Telegraphed `X` spawn markers and Charger/Boss dash warning lanes.
- **Exact Stat & Combat Formulas**:
  - **Armor**: Damage multiplier `15 / (15 + Armor)` (`15 Armor = 50% DR`, negative armor increases damage taken).
  - **Dodge**: Capped at `60%` by default (`90%` for *Ghost*).
  - **HP Regeneration**: `0.20 + (HP_Regen - 1) * (0.8 / 9.0)` HP/sec.
  - **XP Curve**: `(Level + 3)^2` per level; banked level-ups and loot crates resolve cleanly between waves.
  - **Material Bag**: Uncollected materials left on the floor at wave end carry over into the bag and double material drops on the next wave until drained.
  - **Weapon Range & Scaling**: Melee weapons receive `+50%` of the Range stat; Ranged weapons receive `+100%`; per-weapon stat scaling ratios (`Melee`, `Ranged`, `Elemental`, `Engineering`, `Max HP`, `Attack Speed`).
- **12 Distinct Characters**:
  - *Well Rounded*, *Brawler*, *Crazy*, *Ranger*, *Mage*, *Chunky*, *Engineer*, *Ghost*, *One-Armed* (1 weapon slot, +200% Attack Speed), *Multitasker* (12 weapon slots), *Loud*, *Lucky*.
- **27 Weapons & 12 Weapon Class Synergies**:
  - Melee thrust & sweep arcs (`Knife`, `Lightning Shiv`, `Spear`, `Stick`, `Sword`, `Chopper`, `Fist`, `Claw`, `Scissors`, `Ghost Flint`, `Ghost Axe`, `Wrench`, `Screwdriver`, `Pruner`, `Plank`, `Torch`, `Rock`).
  - Ranged projectiles, pellets, bounces, pierces, explosions, burn, and slow (`Pistol`, `SMG`, `Double Barrel Shotgun`, `Slingshot`, `Crossbow`, `Laser Gun`, `Rocket Launcher`, `Wand`, `Taser`, `Ghost Scepter`).
  - Engineering structures (Wrench turrets & Screwdriver landmines).
  - Shop **Combine** (`Tier I -> II -> III -> IV`, including auto-combining when buying into a full loadout) and **Recycle**.
- **38 Tiered Items (Common → Legendary)** with authentic stat tradeoffs, unique item caps, and special triggers (*Piggy Bank*, *Tardigrade*, *Ricochet*, *Bandana*, *Giant Belt*, *Crown*, *Vigilante Ring*, *Fairy*, *Scared Sausage*, *Snake*, *Baby Elephant*, *Cyberball*, *Power Generator*, etc.).

---

## Performance Architecture

- **`SpatialHashGrid` (`src/brotato/spatial_grid.py`)**: `O(1)` spatial cell indexing for enemy separation, weapon auto-aim, melee sweep/thrust queries, projectile collision, explosion AoE, and pickup magnetism.
- **Zero-Allocation Render Caches**: Pre-rendered procedural sprites, quantized angle rotation cache for weapons, and cached text surfaces (`freesansbold.ttf` bundled in Pygame-CE).
- **Fixed-Timestep Decoupled Engine**: Pure simulation in `src/brotato/engine/` separated from rendering in `src/brotato/ui/` (runs at >500 combined simulation + render FPS in headless benchmarks).

---

## Data-Driven Modding & Custom Asset Packs

All game definitions live in editable JSON files under `data/`:
- `data/characters.json`
- `data/weapons.json`
- `data/weapon_classes.json`
- `data/items.json`
- `data/enemies.json`
- `data/waves.json`
- `data/stats_meta.json`

To swap in your own local PNG sprites, WAV/OGG sound effects, or TTF fonts without touching code, drop files into `assets/` following `assets/README_ASSETS.md`.

---

## Running Tests

```bash
pytest -v
```
