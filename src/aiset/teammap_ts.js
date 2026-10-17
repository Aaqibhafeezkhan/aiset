// teammap's TypeScript extractor. Usage: node teammap_ts.js <typescript-module-dir> <repo-root> < file-list
// Prints one JSON object: { "<relpath>": {symbols, types, consts, http, calls, imports}, ... }
// Syntax only (no type checker), so it is fast and works on files that don't compile.
const path = require("path");
const fs = require("fs");
const ts = require(process.argv[2]);
const root = process.argv[3];
const files = fs.readFileSync(0, "utf8").split(/\r?\n/).filter(Boolean);

const HTTP = new Set(["get", "post", "put", "patch", "delete", "request", "head"]);
const out = {};

// a URL expression as tokens: {lit: "..."} | {id: "NAME"} | {param: "expr"}
function urlTokens(node, scope, depth = 0) {
  if (!node || depth > 4) return null;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return [{ lit: node.text }];
  if (ts.isTemplateExpression(node)) {
    const toks = [{ lit: node.head.text }];
    for (const span of node.templateSpans) {
      const e = span.expression;
      if (ts.isIdentifier(e) && /^[A-Z][A-Z0-9_]+$/.test(e.text)) toks.push({ id: e.text });
      else if (ts.isIdentifier(e) && scope && scope[e.text]) toks.push(...(urlTokens(scope[e.text], null, depth + 1) || [{ param: e.text }]));
      else toks.push({ param: e.getText().slice(0, 40) });
      toks.push({ lit: span.literal.text });
    }
    return toks;
  }
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const a = urlTokens(node.left, scope, depth + 1), b = urlTokens(node.right, scope, depth + 1);
    return a && b ? [...a, ...b] : null;
  }
  if (ts.isIdentifier(node)) {
    if (scope && scope[node.text]) return urlTokens(scope[node.text], null, depth + 1);
    return [{ id: node.text }];
  }
  if (ts.isPropertyAccessExpression(node)) return [{ id: node.getText() }];
  // ENDPOINTS.BY_ID(id): the table entry, resolved through consts like a plain ENDPOINTS.LOGIN
  if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) return [{ id: node.expression.getText() }];
  return null;
}

function nameOf(n) {
  if (n.name && (ts.isIdentifier(n.name) || ts.isStringLiteral(n.name))) return n.name.text;
  if (ts.isVariableDeclaration(n.parent) && ts.isIdentifier(n.parent.name)) return n.parent.name.text;
  if (ts.isPropertyAssignment(n.parent) && n.parent.name) return n.parent.name.getText();
  return null;
}

for (const rel of files) {
  let text;
  try { text = fs.readFileSync(path.join(root, rel), "utf8"); } catch { continue; }
  const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, rel.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const line = n => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;
  const endLine = n => sf.getLineAndCharacterOfPosition(n.end).line + 1;
  const f = { symbols: [], types: [], consts: {}, http: [], calls: [], imports: [] };
  const stack = [];  // enclosing symbol names
  const scopes = [{}];  // local `const x = <expr>` per function, for url variables

  function visit(n) {
    let pushed = false, scoped = false;
    if (ts.isImportDeclaration(n) && ts.isStringLiteral(n.moduleSpecifier)) {
      const names = [];
      const c = n.importClause;
      if (c?.name) names.push(c.name.text);
      if (c?.namedBindings && ts.isNamedImports(c.namedBindings)) for (const e of c.namedBindings.elements) names.push(e.name.text);
      f.imports.push({ from: n.moduleSpecifier.text, names });
    }
    if (ts.isInterfaceDeclaration(n) || ts.isTypeAliasDeclaration(n) || ts.isEnumDeclaration(n)) {
      const members = [];
      const list = ts.isInterfaceDeclaration(n) ? n.members : ts.isEnumDeclaration(n) ? n.members
        : (n.type && ts.isTypeLiteralNode(n.type) ? n.type.members : []);
      for (const m of list) {
        if (!m.name) continue;
        members.push({ name: m.name.getText(sf).replace(/['"]/g, ""), type: m.type ? m.type.getText(sf).slice(0, 80) : (m.initializer ? m.initializer.getText(sf).slice(0, 40) : ""), optional: !!m.questionToken });
      }
      f.types.push({ name: n.name.text, kind: ts.isInterfaceDeclaration(n) ? "interface" : ts.isEnumDeclaration(n) ? "enum" : "type", line: line(n), end: endLine(n), members });
    }
    const isFn = ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n);
    if (isFn || ts.isClassDeclaration(n)) {
      const nm = nameOf(n);
      if (nm) {
        const qual = [...stack, nm].join(".");
        const params = isFn ? n.parameters.map(p => p.name.getText(sf)).join(", ") : "";
        // keep top-level functions, class members and object-literal methods; skip inline callbacks
        if (!isFn || stack.length < 2 || ts.isMethodDeclaration(n)) f.symbols.push({ name: nm, qual, kind: ts.isClassDeclaration(n) ? "class" : "function", line: line(n), end: endLine(n), params });
        stack.push(nm); pushed = true;
      }
      if (isFn) { scopes.push({}); scoped = true; }
    }
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer) {
      const init = n.initializer;
      if (stack.length === 0 && (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init) || ts.isTemplateExpression(init) || ts.isBinaryExpression(init)))
        f.consts[n.name.text] = urlTokens(init, null);
      else if (stack.length === 0 && ts.isObjectLiteralExpression(init)) {
        // endpoint tables: { LOGIN: "/auth/login", BY_ID: (id) => `/users/${id}` } -> consts["NAME.KEY"]
        for (const p of init.properties) {
          if (!ts.isPropertyAssignment(p) || !p.name) continue;
          let v = p.initializer;
          if ((ts.isArrowFunction(v) || ts.isFunctionExpression(v)) && !ts.isBlock(v.body)) v = v.body;
          const toks = urlTokens(v, null);
          if (toks && toks.some(t => t.lit)) f.consts[n.name.text + "." + p.name.getText(sf)] = toks;
        }
      }
      else scopes[scopes.length - 1][n.name.text] = init;
    }
    if (ts.isCallExpression(n)) {
      const callee = n.expression;
      const enclosing = stack.join(".") || null;
      if (ts.isPropertyAccessExpression(callee)) {
        const method = callee.name.text, obj = callee.expression.getText(sf);
        f.calls.push({ name: method, obj: obj.slice(0, 60), line: line(n), in: enclosing });
        if (HTTP.has(method) && /(^|\.)\w*(axios|http|api|client|instance|request)$/i.test(obj) && n.arguments.length) {
          const scope = Object.assign({}, ...scopes);
          const toks = urlTokens(n.arguments[0], scope);
          if (toks) f.http.push({ method: method.toUpperCase(), url: toks, line: line(n), in: enclosing });
        }
      } else if (ts.isIdentifier(callee)) {
        f.calls.push({ name: callee.text, line: line(n), in: enclosing });
        if (callee.text === "fetch" && n.arguments.length) {
          const toks = urlTokens(n.arguments[0], Object.assign({}, ...scopes));
          const opt = n.arguments[1];
          let m = "GET";
          if (opt && ts.isObjectLiteralExpression(opt)) for (const p of opt.properties) if (p.name?.getText(sf) === "method" && p.initializer) m = p.initializer.getText(sf).replace(/['"`]/g, "").toUpperCase();
          if (toks) f.http.push({ method: m, url: toks, line: line(n), in: enclosing });
        }
      }
    }
    ts.forEachChild(n, visit);
    if (pushed) stack.pop();
    if (scoped) scopes.pop();
  }
  visit(sf);
  out[rel] = f;
}
process.stdout.write(JSON.stringify(out));
