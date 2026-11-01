# Community botpack (without Wolvot)

This optional pack was assembled from the user's `RLBot_Botpack_2026-10-29_COMPLET.zip` archive. **All Wolvot variants and the original Wolvot archive are intentionally excluded** until the correct Wolvot version is identified. The source folders, bot configurations, model files and binaries listed below have otherwise been kept as supplied.

| Folder | Contents | Runtime |
| --- | --- | --- |
| `BOT_RLBOT_V4/Element` | Element + model | RLBot V4 |
| `BOT_RLBOT_V4/Necto` | Necto + model | RLBot V4 |
| `BOT_RLBOT_V4/Nexto` | Nexto + model | RLBot V4 |
| `MECH_VERSIONS_UNCONFIRMED/` | Three separate Mech candidates; **not confirmed as MechV7** | RLBot V4 |
| `WISP_RLBOT_V5/WispV2_binary` | Wisp V2 Windows executable and config | RLBot V5; Wine/Proton on Linux |
| `WISP_RLBOT_V5/WispV2_source` | Wisp V2 source, model and config | RLBot V5; build may be required |
| `LICENCES/` | License text supplied with the original archive | — |

## Download and import

The GitHub Release provides a separate `EvilRLBot-Community-Botpack-No-Wolvot-<version>.zip`. In Evil RLBot choose **Import archive**, then select this ZIP (or import a specific bot folder/config). The pack is intentionally **not auto-executed, auto-imported or bundled inside the standard installer/AppImage**. Existing bot libraries are not overwritten. Some bots require dependency installation, a supported Python runtime, or Wine/Proton; the presence of a bot config does not certify it works in game.

## Third-party code and licenses

These are independent community bots, not code authored or endorsed by Evil RLBot. Preserve each upstream project's notices and license requirements. In particular, the supplied Necto license is **CC BY-NC-SA 4.0** (which has non-commercial and attribution/share-alike conditions); Wisp V2 source includes an MIT license and a README with a no-cheating restriction. Do not assume Evil RLBot's application license supersedes any bot's license. Mech version attribution remains unverified. Review third-party executable files and PyTorch model files before running them. The Wisp binary has **not** been executed or security-audited as part of packaging.

The archive was provided as-is. See `README.txt` for the original inventory and verification limitations.