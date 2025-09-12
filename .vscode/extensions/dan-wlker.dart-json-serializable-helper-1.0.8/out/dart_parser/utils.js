"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.findProjectName = exports.includesAll = exports.includesOne = exports.indent = exports.removeStart = exports.count = exports.readSetting = exports.getEditor = exports.isBlank = exports.areStrictEqual = exports.removeEnd = exports.toVarName = void 0;
const vscode = require("vscode");
const globalVar_1 = require("./globalVar");
const fs = require("fs");
function toVarName(source) {
    let s = source;
    let r = "";
    let replace = (char) => {
        if (s.includes(char)) {
            const splits = s.split(char);
            for (let i = 0; i < splits.length; i++) {
                let w = splits[i];
                i > 0 ? (r += capitalize(w)) : (r += w);
            }
        }
    };
    // Replace invalid variable characters like '-'.
    replace("-");
    replace("~");
    replace(":");
    replace("#");
    replace("$");
    if (r.length === 0) {
        r = s;
    }
    // Prevent dart keywords from being used.
    switch (r) {
        case "assert":
            r = "aAssert";
            break;
        case "break":
            r = "bBreak";
            break;
        case "case":
            r = "cCase";
            break;
        case "catch":
            r = "cCatch";
            break;
        case "class":
            r = "cClass";
            break;
        case "const":
            r = "cConst";
            break;
        case "continue":
            r = "cContinue";
            break;
        case "default":
            r = "dDefault";
            break;
        case "do":
            r = "dDo";
            break;
        case "else":
            r = "eElse";
            break;
        case "enum":
            r = "eEnum";
            break;
        case "extends":
            r = "eExtends";
            break;
        case "false":
            r = "fFalse";
            break;
        case "final":
            r = "fFinal";
            break;
        case "finally":
            r = "fFinally";
            break;
        case "for":
            r = "fFor";
            break;
        case "if":
            r = "iIf";
            break;
        case "in":
            r = "iIn";
            break;
        case "is":
            r = "iIs";
            break;
        case "new":
            r = "nNew";
            break;
        case "null":
            r = "nNull";
            break;
        case "rethrow":
            r = "rRethrow";
            break;
        case "return":
            r = "rReturn";
            break;
        case "super":
            r = "sSuper";
            break;
        case "switch":
            r = "sSwitch";
            break;
        case "this":
            r = "tThis";
            break;
        case "throw":
            r = "tThrow";
            break;
        case "true":
            r = "tTrue";
            break;
        case "try":
            r = "tTry";
            break;
        case "var":
            r = "vVar";
            break;
        case "void":
            r = "vVoid";
            break;
        case "while":
            r = "wWhile";
            break;
        case "with":
            r = "wWith";
            break;
    }
    if (r.length > 0 && r[0].match(new RegExp(/[0-9]/))) {
        r = "n" + r;
    }
    return r;
}
exports.toVarName = toVarName;
function capitalize(source) {
    let s = source;
    if (s.length > 0) {
        if (s.length > 1) {
            return s.substr(0, 1).toUpperCase() + s.substring(1, s.length);
        }
        else {
            return s.substr(0, 1).toUpperCase();
        }
    }
    return s;
}
function removeEnd(source, end) {
    if (Array.isArray(end)) {
        let result = source.trim();
        for (let e of end) {
            result = removeEnd(result, e).trim();
        }
        return result;
    }
    else {
        const pos = source.length - end.length;
        return source.endsWith(end) ? source.substring(0, pos) : source;
    }
}
exports.removeEnd = removeEnd;
function areStrictEqual(a, b) {
    let x = a.replace(/\s/g, "");
    let y = b.replace(/\s/g, "");
    return x === y;
}
exports.areStrictEqual = areStrictEqual;
function isBlank(str) {
    return !str || /^\s*$/.test(str);
}
exports.isBlank = isBlank;
function getEditor() {
    return vscode.window.activeTextEditor;
}
exports.getEditor = getEditor;
function readSetting(key) {
    return vscode.workspace
        .getConfiguration()
        .get("dart_json_serializable_helper." + key);
}
exports.readSetting = readSetting;
function count(source, match) {
    let count = 0;
    let length = match.length;
    for (let i = 0; i < source.length; i++) {
        let part = source.substr(i * length - 1, length);
        if (part === match) {
            count++;
        }
    }
    return count;
}
exports.count = count;
function removeStart(source, start) {
    if (Array.isArray(start)) {
        let result = source.trim();
        for (let s of start) {
            result = removeStart(result, s).trim();
        }
        return result;
    }
    else {
        return source.startsWith(start)
            ? source.substring(start.length, source.length)
            : source;
    }
}
exports.removeStart = removeStart;
function indent(source) {
    let r = "";
    for (let line of source.split("\n")) {
        r += "  " + line + "\n";
    }
    return r.length > 0 ? r : source;
}
exports.indent = indent;
function includesOne(source, matches, wordBased = true) {
    const words = wordBased ? source.split(" ") : [source];
    for (let word of words) {
        for (let match of matches) {
            if (wordBased) {
                if (word === match) {
                    return true;
                }
            }
            else {
                if (source.includes(match)) {
                    return true;
                }
            }
        }
    }
    return false;
}
exports.includesOne = includesOne;
function includesAll(source, matches) {
    for (let match of matches) {
        if (!source.includes(match)) {
            return false;
        }
    }
    return true;
}
exports.includesAll = includesAll;
async function findProjectName() {
    const pubspecs = await vscode.workspace.findFiles("pubspec.yaml");
    if (pubspecs !== null && pubspecs.length > 0) {
        const pubspec = pubspecs[0];
        const content = fs.readFileSync(pubspec.fsPath, "utf8");
        if (content !== null && content.includes("name: ")) {
            globalVar_1.default.isFlutter =
                content.includes("flutter:") && content.includes("sdk: flutter");
            for (const line of content.split("\n")) {
                if (line.startsWith("name: ")) {
                    globalVar_1.default.projectName = line.replace("name:", "").trim();
                    break;
                }
            }
        }
    }
}
exports.findProjectName = findProjectName;
//# sourceMappingURL=utils.js.map