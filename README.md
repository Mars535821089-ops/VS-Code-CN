# Visual Studio Code Language Packs

Visual Studio Code is localized into many different languages using the concept of Language Packs. Language Packs can be installed by running the `>Configure Display Language` command in Visual Studio Code's Command Palette or installed via the [Visual Studio Code Marketplace](https://marketplace.visualstudio.com/search?target=VSCode&category=Language%20Packs&sortBy=Installs).

The original English strings can be found in the source code of the [open source repository](https://github.com/microsoft/vscode), and the localized strings for supported languages can be found in this repository.

Localized resource files are managed and edited by Microsoft. Files will be exported to this repository when strings are updated to prepare for the publishing of language packs.

There are currently 14 supported languages for Visual Studio Code.

|Language|Visual Studio Code Language ID|MLCP Language Code|
|--------|--------|--------|
|**French**|fr|French (fr-fr)
|**Italian**|it|Italian (it-it)
|**German**|de|German (de-de)
|**Spanish**|es|Spanish (es-es)
|**Russian**|ru|Russian (ru-ru)
|**Chinese (Simplified)**|zh-cn|Chinese Simplified (zh-cn)
|**Chinese (Traditional)**|zh-tw|Chinese Traditional (zh-tw)
|**Japanese**|ja|Japanese (ja-jp)
|**Korean**|ko|Korean (ko-kr)
|**Czech**|cs|Czech (cs-CZ)
|**Portuguese (Brazil)**|pt-br|Portuguese (Brazil) (pt-br)
|**Turkish**|tr|Turkish (tr-tr)
|**Polish**|pl|Polish (pl-pl)
|**Pseudo Language**|qps-ploc|Pseudo (qps-ploc)

## This fork

This repository is a fork of [microsoft/vscode-loc](https://github.com/microsoft/vscode-loc), the upstream home for VS Code language-pack resources. Translation strings under `i18n` are managed by Microsoft and preserved unchanged. This fork also contains an independent, non-installing incremental audit tool described below; it does not contain the VS Code application source.

For Simplified Chinese in VS Code, install the official [Chinese (Simplified) Language Pack](https://marketplace.visualstudio.com/items?itemName=MS-CEINTL.vscode-language-pack-zh-hans), then run **Configure Display Language** from the Command Palette and select Chinese (Simplified).

The **Sync upstream** GitHub Actions workflow merges `microsoft/vscode-loc`'s `main` branch into this repository's default branch every day. It can also be started manually from the Actions tab. The workflow never force-pushes: merge conflicts or branch protection rules stop the run without replacing fork content; resolve them before retrying.

### Auditing newer VS Code builds

The official language pack can be compatible with a newer VS Code release while still missing its new strings. The independent, reviewed supplement in `tools/localization/reviewed-zh-cn.json` is not a Microsoft release. It does not change the upstream `i18n` resources or the installed extension.

On macOS, generate a reproducible audit and supplemental resources (Python 3, no dependencies):

```sh
python3 tools/localization/build_incremental.py \
  --app "/Applications/Visual Studio Code.app/Contents/Resources/app" \
  --output /tmp/vscode-zh-cn-audit
python3 -m unittest discover -s tools/localization -p 'test_*.py' -v
```

The output directory must not already exist. `audit.json` contains the exact build, input hashes, every applied module/key with provenance, explicitly preserved names/format-only strings, and the complete remaining candidate list. Missing modules, missing keys, empty values, and unchanged official English are counted separately. Unchanged English is a review candidate, not proof of a defect (for example, keyboard names and product identifiers can remain English).

`delta.json` contains only additions; `merged-main.i18n.json` preserves every existing non-empty official value. Automatic reuse requires the same key and exact English source, one unambiguous Chinese translation in the official resources, and matching formatting tokens. Reviewed entries match exact English sources; placeholders, code spans, links, tags, icon tokens, settings references, newlines and mnemonic markers are validated. New or ambiguous strings stay in the report rather than being machine-translated.

These are **review artifacts, not a language pack installed for your user**. The generator does not produce an extension manifest or Microsoft publisher identity. Do not copy resources into VS Code's `out` directory or overwrite the official extension. New build coverage requires rerunning the audit. Review the remaining module/key contexts before adding translations.

On 2026-10-30, the audit of stable 1.144.0 (`2c33b50b16c472efe58357d1d2a8a5414bc23fbf`) against official pack `1.131.2026090407` found 30,566 runtime occurrences representing 30,514 distinct module/key pairs. The reviewed dictionary and conservative official reuse produced **877 distinct supplemental translations** (860 reviewed, 17 reused). Another 208 candidates were preserved as exact names or format-only strings. **8,880 candidates remain for review**: 2,468 missing keys in existing modules, 3,944 keys in absent modules, and 2,468 unchanged official English values. These counts describe generated resources, not current-user or visually verified coverage.

### Isolated registration and runtime verification

With Node.js and the installed VS Code CLI available, verify generated artifacts without opening an editor window:

```sh
python3 tools/localization/verify_isolated.py \
  --app "/Applications/Visual Studio Code.app/Contents/Resources/app" \
  --official-extension "$HOME/.vscode/extensions/ms-ceintl.vscode-language-pack-zh-hans-1.131.2026090407" \
  --generated /tmp/vscode-zh-cn-audit \
  --output /tmp/vscode-zh-cn-verification
```

The verification output directory must be new; the generated audit directory must already exist. The verifier installs two unsigned, code-free test fixtures with publisher `local-vscode-cn-audit` into temporary `--user-data-dir` / `--extensions-dir` directories, with sync explicitly disabled. It copies official resources locally for comparison, never publishes or uploads them, and removes all temporary fixtures afterwards. No Microsoft extension identity or signature is used.

**Observed CLI limitation:** installing these fixtures succeeds but does not create `languagepacks.json`. The test therefore executes the installed `cliProcessMain.js` cache registration methods on the CLI-persisted extension manifest order, then executes the installed `cli.js` NLS resolver with real filesystem dependencies. The extracted methods are not rewritten; their SHA-256 hashes and the CLI bundle hash are recorded. Extraction is specific to 1.144.0 and fails explicitly if its anchors change. This is runtime implementation verification, **not GUI scanning-order or visual acceptance**.

Testing both orders proves that the last registered resource ID wins for the same locale; VS Code does not merge core strings from two language packs key by key. In the merged-last case, all 877 additions load and all 30,566 compiled messages match the selected resources or English fallback. In the baseline-last case, zero additions load. The 95 registered translation resource IDs are retained and parseable. Regional-locale fallback, absent-locale fallback, explicit English and cache reload are checked. The verifier also checks hashes of 103 application, official resource and current-user registration/configuration files before and after the test.

**Do not install a second pack contributing the same `zh-cn` core resource.** Startup ordering could discard all additions or select a stale resource. Use the independent locale below instead. Remaining missing strings still fall back to English; this project does not claim complete translation.

### Independent `zh-cn-mars` locale

The independent extension `mars-localization.vscode-language-pack-zh-cn-mars` contributes **only `zh-cn-mars`**, not `zh-cn`. It contains all 95 official translation resources with the reviewed core additions. It is unsigned and local-only, does not use a Microsoft publisher identity, and leaves the official extension installed and unchanged.

Generate and verify it after generating the audit above:

```sh
python3 tools/localization/custom_pack.py \
  --app "/Applications/Visual Studio Code.app/Contents/Resources/app" \
  --official-extension "$HOME/.vscode/extensions/ms-ceintl.vscode-language-pack-zh-hans-1.131.2026090407" \
  --generated /tmp/vscode-zh-cn-audit \
  --output /tmp/vscode-mars-package
python3 tools/localization/verify_isolated.py \
  --app "/Applications/Visual Studio Code.app/Contents/Resources/app" \
  --official-extension "$HOME/.vscode/extensions/ms-ceintl.vscode-language-pack-zh-hans-1.131.2026090407" \
  --generated /tmp/vscode-zh-cn-audit \
  --custom-vsix /tmp/vscode-mars-package/mars-localization.vscode-language-pack-zh-cn-mars-0.1.0.vsix \
  --output /tmp/vscode-mars-verification
```

In both installation orders, the installed registration/NLS implementations resolve `zh-cn-mars` to the custom resource and load all 877 additions. Both locales remain registered independently. If the custom registration is absent, `zh-cn-mars` falls back to `zh-cn`. Explicit startup locale selection is passed to NLS without the OS-language normalization that would otherwise collapse a Chinese variant. All official non-empty translations are preserved. Package generation checks the audit/build/input hashes, validates that the merged core is exactly the official baseline plus audited additions, and produces byte-identical VSIX output for identical inputs.

This validation targets macOS and the core NLS/registered translation resources. Third-party extensions may implement their own locale matching or webview translations and may not recognize a custom locale; their UI is not guaranteed to change. Restore official `zh-cn` if such an extension regresses. No visual acceptance or cross-platform compatibility is claimed.

The engine is deliberately pinned to **exactly 1.144.0**, not `^1.144.0`; later releases need a new build audit and compatibility review. VS Code's engine parser rejects compound ranges, so the exact version is used. Do not bypass compatibility checks when updating VS Code.

After isolated verification succeeds, install the independent extension and configure the next startup:

```sh
code --install-extension /tmp/vscode-mars-package/mars-localization.vscode-language-pack-zh-cn-mars-0.1.0.vsix --do-not-sync
python3 tools/localization/set_locale.py activate \
  --backup "$HOME/.vscode/mars-startup-locale-backup.json"
```

`set_locale.py` changes only `locale` in `$HOME/.vscode/argv.json`, the startup configuration actually read by this VS Code build. It preserves comments and unrelated settings, refuses duplicate keys, and backs up only the prior locale's presence/value, not crash-report identifiers or other configuration. It does not restart VS Code. An existing backup is never overwritten; retain it across updates.

**Installation is not immediate activation.** The CLI registers the extension but did not refresh `Code/languagepacks.json` in the observed build. After a normal user-initiated quit and relaunch, VS Code can scan the new extension and refresh that cache. If startup NLS resolution happened before the refreshed registration, that launch safely uses official `zh-cn`; a subsequent normal relaunch may be required. Verify that `languagepacks.json` has `zh-cn-mars` and its `vscode` path points to the independent extension, and that a compiled `clp` cache exists, before reporting the supplement active. Do not manually replace the user's registration cache or assume a window reload rereads startup arguments.

Restore the previous startup locale without reverting unrelated settings:

```sh
python3 tools/localization/set_locale.py restore \
  --backup "$HOME/.vscode/mars-startup-locale-backup.json"
code --uninstall-extension mars-localization.vscode-language-pack-zh-cn-mars --do-not-sync
```

Restoration refuses to overwrite a locale the user changed after activation. If the previous configuration had no explicit locale, it removes only the added locale and returns to automatic language selection. To explicitly select official Simplified Chinese, use **Configure Display Language** and choose the official Chinese pack, or start a fresh VS Code process with `--locale=zh-cn`. No current window is closed or restarted by the scripts.

## Contributing

If you want to give feedback or report an issue with a translation, please create a [new GitHub issue](https://github.com/microsoft/vscode-loc/issues/new). Please check if a topic about your issue already exists!
Translation strings are managed on the Microsoft Localization Platform, and changes to strings can only be made there. Consequently, pull requests fixing translations won't be accepted. All other PRs to things like `README.md`, `package.json`, etc., will be accepted at the discretion of the maintainers.

## Legal

Before we can accept your pull request, you will need to sign a **Contribution License Agreement**. All you need to do is submit a pull request. It will then be appropriately labeled (e.g., `cla-required`, `cla-norequired`, `cla-signed`, `cla-already-signed`). If you already signed the agreement, we will continue with reviewing the PR; otherwise, our system will tell you how you can sign the CLA. Once you sign the CLA, all future PRs will be labeled as `cla-signed`.

# Microsoft Open Source Code of Conduct

This project has adopted the [**Microsoft Open Source Code of Conduct**](https://opensource.microsoft.com/codeofconduct/).
For more information, see the [**Code of Conduct FAQ**](https://opensource.microsoft.com/codeofconduct/faq/) or contact [**opencode@microsoft.com**](mailto:opencode@microsoft.com) with any additional questions or comments.

## License

[MIT](LICENSE.md)
