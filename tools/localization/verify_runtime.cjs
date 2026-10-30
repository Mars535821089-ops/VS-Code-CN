// Execute the installed 1.144.0 NLS resolver without starting an editor window.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const os = require('node:os');

async function main() {
  const [app, userData, generated, extensions] = process.argv.slice(2);
  assert.ok([app, userData, generated, extensions].every(Boolean), 'Four explicit paths required');
  const temporary = fs.realpathSync(os.tmpdir()) + path.sep;
  for (const candidate of [userData, extensions]) {
    assert.ok(fs.realpathSync(candidate).startsWith(temporary), 'Verification data must be in a temporary directory');
  }
  const product = JSON.parse(fs.readFileSync(path.join(app, 'product.json')));
  const packageJson = JSON.parse(fs.readFileSync(path.join(app, 'package.json')));
  assert.equal(packageJson.version, '1.144.0', 'Resolver extraction is version-specific; review before adapting.');
  const cli = fs.readFileSync(path.join(app, 'out/cli.js'), 'utf8');
  const start = cli.indexOf('async function Po({userLocale:');
  const end = cli.indexOf('var Ac=await Po(', start);
  assert.ok(start >= 0 && end > start, 'Installed resolver extraction anchors changed');
  const resolverSource = cli.slice(start, end);
  // CLI VSIX installation can finish without constructing the language-pack
  // service. Exercise the installed registration implementation explicitly.
  const registryFile = path.join(userData, 'languagepacks.json');
  const cliCreatedRegistry = fs.existsSync(registryFile);
  const registrationBundle = fs.readFileSync(path.join(app, 'out/vs/code/node/cliProcessMain.js'), 'utf8');
  const methodsStart = registrationBundle.indexOf('createLanguagePacksFromExtensions(e,...n){');
  const methodsEnd = registrationBundle.indexOf('withLanguagePacks(e=', methodsStart);
  const validatorStart = registrationBundle.indexOf('function A1(i){', methodsEnd);
  const validatorEnd = registrationBundle.indexOf('function M1(', validatorStart);
  assert.ok(methodsStart >= 0 && methodsEnd > methodsStart &&
    validatorStart > methodsEnd && validatorEnd > validatorStart, 'Registration extraction anchors changed');
  const registrationSource = registrationBundle.slice(methodsStart, methodsEnd);
  const cache = vm.runInNewContext(
    `${registrationBundle.slice(validatorStart, validatorEnd)}; new (class {${registrationSource}})()`,
    { H: path.join, $: { file: 'file' }, _1: crypto.createHash,
      Q: (a, b) => a.id.toLowerCase() === b.id.toLowerCase() },
    { timeout: 5000 });
  const installed = JSON.parse(fs.readFileSync(path.join(extensions, 'extensions.json')));
  const extensionObjects = installed.map(item => {
    const folder = path.resolve(item.location.path);
    assert.ok(folder.startsWith(path.resolve(extensions) + path.sep));
    return { identifier: item.identifier,
      manifest: JSON.parse(fs.readFileSync(path.join(folder, 'package.json'))),
      location: { scheme: 'file', fsPath: folder } };
  });
  const registered = {};
  cache.createLanguagePacksFromExtensions(registered, ...extensionObjects);
  fs.mkdirSync(userData, { recursive: true });
  fs.writeFileSync(registryFile, JSON.stringify(registered));
  const resolver = vm.runInNewContext(`${resolverSource}; Po`, {
    Ne: fs.promises, W: path.join, le: { exists: fs.existsSync },
    Ce: () => {}, process: { env: {} }, console,
  }, { timeout: 5000 });
  const baseArgs = {
    userLocale: 'zh-cn', osLocale: 'en', userDataPath: userData,
    commit: product.commit, nlsMetadataHash: product.nlsMetadataHash,
    nlsMetadataPath: path.join(app, 'out'),
  };
  const resolved = await resolver(baseArgs);
  assert.equal(resolved.resolvedLanguage, 'zh-cn');
  const load = file => JSON.parse(fs.readFileSync(file, 'utf8'));
  const compiled = load(resolved.languagePack.messagesFile);
  const registry = load(path.join(userData, 'languagepacks.json'));
  const selected = load(registry['zh-cn'].translations.vscode);
  const keys = load(path.join(app, 'out/nls.keys.json'));
  const english = load(path.join(app, 'out/nls.messages.json'));
  const audit = load(path.join(generated, 'audit.json'));
  const additions = new Map(audit.applied.map(x => [JSON.stringify([x.module, x.key]), x.translation]));
  const applied = new Set();
  let index = 0, fallbacks = 0;
  for (const [module, moduleKeys] of keys) {
    for (const key of moduleKeys) {
      const expected = selected.contents[module]?.[key] || english[index];
      assert.equal(compiled[index], expected, `${module}/${key}`);
      if (!selected.contents[module]?.[key]) {
        assert.equal(compiled[index], english[index]);
        fallbacks++;
      }
      const pair = JSON.stringify([module, key]);
      if (additions.has(pair) && compiled[index] === additions.get(pair)) applied.add(pair);
      index++;
    }
  }
  assert.equal(index, compiled.length);
  assert.equal(index, english.length);
  assert.equal((await resolver({ ...baseArgs, userLocale: 'zh-cn-audit' })).resolvedLanguage, 'zh-cn');
  assert.equal((await resolver({ ...baseArgs, userLocale: 'zz-audit' })).resolvedLanguage, 'en');
  assert.equal((await resolver({ ...baseArgs, userLocale: 'en' })).resolvedLanguage, 'en');
  // Cached reload must resolve to the same compiled messages.
  assert.equal((await resolver(baseArgs)).languagePack.messagesFile, resolved.languagePack.messagesFile);
  console.log(JSON.stringify({
    runtime_occurrences_verified: index, applied_loaded: applied.size,
    english_fallback_occurrences: fallbacks,
    regional_fallback_verified: true, missing_locale_fallback_verified: true,
    english_locale_verified: true, cache_reload_verified: true,
    cli_sha256: crypto.createHash('sha256').update(cli).digest('hex'),
    resolver_sha256: crypto.createHash('sha256').update(resolverSource).digest('hex'),
    registration_sha256: crypto.createHash('sha256').update(registrationSource).digest('hex'),
    registration_input_order: installed.map(item => item.identifier.id),
    cli_created_registry: cliCreatedRegistry,
    registration_mode: 'Installed cache methods, using CLI-persisted extension manifest order; not GUI scanner verification.',
  }, null, 2));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
