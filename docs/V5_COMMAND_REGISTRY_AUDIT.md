# Aetheris V5 Command Registry & Collision Audit

**Generated**: 2026-09-04 | **Release Stage**: `5.0.0-rc2`

## 1. Command Reconciliation Summary

- **RC1 Baseline Command Count**: `396` (Derived from naive static AST regex)
- **RC2 Runtime Registered Commands**: `495` (Full dynamic import & atomic unbind verification)
- **Unique Command Triggers**: `476`
- **Net Command Delta**: `+99` commands

### Delta Classification Breakdown

| Classification | Count | Description |
| :--- | :--- | :--- |
| `newly_introduced_v5_command` | 40 | Commands added in 8 new V5 subsystem plugins (AI powerhouse, Cyber tools, etc.) |
| `duplicate_discovered_differently` | 6 | Command triggers registered across multiple plugins that were de-duplicated in RC1 |
| `genuine_command_previously_missed` | 53 | Commands with multi-line tuples/kwargs missed by RC1 static AST inspection |
| **Total Reconciled Delta** | **99** | **100% of the +99 command increase fully explained** |

## 2. Cross-Plugin Duplicate Trigger Audit

The runtime validation identified 19 command triggers that are implemented in more than one plugin.
In Telethon, multiple handlers for the same pattern execute in registration order unless filtered.
Aetheris V5 scopes each handler to its specific plugin ID (`plugin:command:id`) in `atomic_registry`.

| Command Trigger | Occurrence Count | Implementing Plugins | Conflict Resolution / Routing |
| :--- | :--- | :--- | :--- |
| `.anime` | 2 | `ai_powerhouse, anilist` | V5 AI powerhouse supersedes legacy anime search if configured |
| `.blur` | 2 | `image_magic, poto` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.cur` | 2 | `tools, ultroid_power` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.delayspam` | 2 | `admin_nuke_defense, spam` | Anti-nuke rate-limited delayspam overrides unmanaged spam loop |
| `.dice` | 2 | `emojigames, social_fun` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.flip` | 2 | `memify, social_fun` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.hash` | 2 | `hash, ultroid_power` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.ip` | 2 | `cyber_tools, tools` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.json` | 2 | `hikka_resilience, json` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.lyrics` | 2 | `cyber_tools, lyrics` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.paste` | 2 | `pastebin, ultroid_power` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.purgeme` | 2 | `account_powers, purge` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.reload` | 2 | `corecmds, vps` | Corecmds restart handles process supervisor; VPS handles container |
| `.short` | 2 | `fun_modern, urltools` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.song` | 2 | `download_modern, songs` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.ss` | 2 | `fun_modern, screenshot` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.ud` | 2 | `dictionary, ultroid_power` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.var` | 2 | `heroku, vps` | Priority to primary plugin; secondary executes if propagation not stopped |
| `.weather` | 2 | `climate, cyber_tools` | Priority to primary plugin; secondary executes if propagation not stopped |

## 3. Shadowing & Alias Audit

- **Sudo / Owner Namespace**: Commands flagged `allow_sudo=True` are registered on both owner and sudo prefixes without namespace collisions.
- **Prefix Isolation**: `COMMAND_HAND_LER` and `SUDO_COMMAND_HAND_LER` are independently compiled in regex trees.
- **Zero Legacy/V5 Collisions**: Legacy decorators wrap through `register_legacy_command` into `atomic_registry` with zero dropped or duplicate event listeners.
