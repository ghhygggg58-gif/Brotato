# Custom Asset Pack Support

This directory lets you override the built-in procedural sprites, sound effects, and fonts with your own local art/audio files without modifying any Python code.

## Directory Layout

- `assets/sprites/characters/<character_id>.png` — Custom potato character sprite (recommended 64x64 transparent PNG)
- `assets/sprites/weapons/<weapon_id>.png` — Custom weapon sprite (recommended 48x48 transparent PNG, pointing right `+X`)
- `assets/sprites/enemies/<enemy_id>.png` — Custom enemy sprite (recommended 56x56 transparent PNG)
- `assets/sprites/items/<item_id>.png` — Custom item icon (recommended 48x48 transparent PNG)
- `assets/sprites/arena/floor.png` — Optional tileable arena floor texture (recommended 128x128 or 256x256 PNG)
- `assets/sounds/<sfx_name>.wav` (or `.ogg`) — Overrides for SFX (`shoot`, `melee`, `hit`, `crit`, `hurt`, `pickup`, `levelup`, `buy`, `reroll`, `explosion`, `crate`, `boss`)
- `assets/fonts/main.ttf` — Custom UI & HUD font

Any missing files automatically fall back to the built-in procedural high-contrast vector renderer and synthesized audio engine.
