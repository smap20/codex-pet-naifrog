# Sources and modifications

## Original standard pet

The standard `pet/spritesheet.webp` is the previously installed fallback/listing sheet from https://github.com/timerring/codex-pet-naiwa. The original MIT license is preserved in `licenses/LICENSE`. It is not the full v4.4 animation atlas.

## Seven MyNaiwa clips

Source: https://github.com/SeracLi/MyNaiwa at commit `1f11260996f5fd1466316ba9b97941a8096c80c3`. Exact repository paths and Git blob identifiers are in `source/my-naiwa-sources.json`. Upstream supplied no LICENSE file at the recorded commit; this bundle preserves that status and does not describe these assets as MIT or public domain.

Used clips: idle, scratch, listen, talk, belly, dizzy, float. Transformations: background extraction, source-based moving-pupil alpha repair, one fixed scale/anchor, lossless atlas assembly. Original frame order and durations are preserved.

## Legacy laugh

Source video: https://github.com/CHENGONGSHUO/Naiwa/blob/master/Assets/Video/Naiwa.mp4, SHA-256 `1c05a2a8af2052f2f0a5909f917cf3f1146215a3e5b51542a2f349dc05987e08`.

Upstream processing: https://github.com/dcjaychou-design/NaiWaPet at commit `1c74145ff4abaacdb0e3f5a18660c260d13e5562`. Upstream declares GPL-3.0; full text and its asset provenance are in `licenses/`. The source video and processing-code records are included in `source/`.

Modifications: white-background extraction, protected raised-hand negative spaces, restoration of source hand/toe/eye pixels, identical fixed transform with extended toe coverage, lossless assembly of all 462 frames. No synthetic replacement motion.

## Local extension

`runtime/` and `install.py` implement the local optional atlas player, pointer-held floating behavior, version checking, offline patching, backup and rollback. They are provided as readable source for this package. No OpenAI application binary is redistributed. These files do not change the license status of the source character assets.

Historical provenance is preserved without asserting a broader license than the sources provide. The installer does not download or send data.

## v4.5 playback change

The v4.4 atlas is byte-identical. Only the optional sustained-gesture timeline was added: one introduction, loop original scratch frames22–49, finish from the displayed pose on exit, reverse partial raises or lowering on interrupted transitions. No new image synthesis or matte edits.
