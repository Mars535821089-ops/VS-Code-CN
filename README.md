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

These are **review artifacts, not an installed language pack**. No extension manifest or Microsoft publisher identity is generated. Do not copy them into VS Code's `out` directory or overwrite the official extension. Same-locale language-pack precedence and isolated extension loading have not been verified; installation is intentionally not automated. New build coverage requires rerunning the audit. Review the remaining module/key contexts before adding translations.

On 2026-10-30, the audit of stable 1.144.0 (`2c33b50b16c472efe58357d1d2a8a5414bc23fbf`) against official pack `1.131.2026090407` found 30,566 runtime occurrences representing 30,514 distinct module/key pairs. The 212 reviewed dictionary entries and conservative official reuse produced **689 distinct supplemental translations** (672 reviewed, 17 reused). Another 198 candidates were preserved as exact names or format-only strings. **9,078 candidates remain for review**: 2,536 missing keys in existing modules, 4,068 keys in absent modules, and 2,474 unchanged official English values. These counts describe generated resources, not installed or visually verified coverage.

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
