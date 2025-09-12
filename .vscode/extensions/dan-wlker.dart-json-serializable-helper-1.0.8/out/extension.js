"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = void 0;
const vscode = require("vscode");
const path = require("path");
const utils_1 = require("./dart_parser/utils");
const data_class_generator_1 = require("./dart_parser/data_class_generator");
function activate(context) {
    console.log("dart-json-serializable-helper is now active!");
    // Quick fix provider
    context.subscriptions.push(vscode.languages.registerCodeActionsProvider("dart", new QuickFixJsonSerializableProvider()));
    context.subscriptions.push(vscode.commands.registerCommand("dartJsonSerializableHelper.quickFixJsonSerializable", (document, range) => {
        quickFixJsonSerializableDataClassVer(document, range);
    }));
    (0, utils_1.findProjectName)();
}
exports.activate = activate;
class QuickFixJsonSerializableProvider {
    getClass(generator, lineNumber) {
        for (let clazz of generator.clazzes) {
            let startsAtLine = clazz.startsAtLine;
            // let endsAtLine = clazz.endsAtLine;
            if (startsAtLine === null) {
                //|| endsAtLine === null) {
                continue;
            }
            if (startsAtLine === lineNumber) {
                // && endsAtLine >= lineNumber) {
                return clazz;
            }
        }
        return null;
    }
    isCursorOnClass(clazz, lineNumber) {
        if (clazz === null) {
            return false;
        }
        if (!clazz.isValid) {
            return false;
        }
        return lineNumber === clazz.startsAtLine;
    }
    provideCodeActions(document, range, context, token) {
        const codeActions = [];
        let generator = new data_class_generator_1.DataClassGenerator(document.getText());
        let lineNumber = range.start.line + 1;
        let clazz = this.getClass(generator, lineNumber);
        // Check if the cursor position is on a Dart class and only has one class in the file
        if (generator.clazzes.length === 1 &&
            this.isCursorOnClass(clazz, lineNumber)) {
            const action = new vscode.CodeAction("Generate @JsonSerializable class template", vscode.CodeActionKind.QuickFix);
            action.command = {
                title: "Generate @JsonSerializable class template",
                command: "dartJsonSerializableHelper.quickFixJsonSerializable",
                arguments: [document, range],
            };
            codeActions.push(action);
        }
        return codeActions;
    }
}
function quickFixJsonSerializableDataClassVer(document, range) {
    let documentText = document.getText();
    // Constant stuff that we will definitely need
    const fileUri = document.uri;
    const fileName = path.basename(fileUri.fsPath, path.extname(fileUri.fsPath));
    let jsonSerializableHeaderImport = "import 'package:json_annotation/json_annotation.dart';";
    let jsonSerializableHeaderPart = `part '${fileName}.g.dart';`;
    let jsonSerializableHeaderNotation = "@JsonSerializable()";
    // prettier-ignore
    let jsonSerializableCombinedText = `\
${documentText.includes(jsonSerializableHeaderImport) ? "" : `${jsonSerializableHeaderImport}\n`}\
${documentText.includes(jsonSerializableHeaderPart) ? "" : `${jsonSerializableHeaderPart}\n`}\

${jsonSerializableHeaderNotation}`;
    // Start using class generator
    let generator = new data_class_generator_1.DataClassGenerator(documentText);
    let firstDartClass = generator.clazzes[0];
    // imports
    let imports = (0, utils_1.removeEnd)(generator.imports.formatted, "\n");
    // whole class line
    let classNameLine = (0, utils_1.removeEnd)(firstDartClass.getClassNameLine(), "\n");
    // class name
    let className = firstDartClass.name;
    // variables
    let variables = (0, utils_1.removeEnd)(firstDartClass.propertiesStringList.join(""), "\n");
    // constructor
    let constructor = firstDartClass.getConstructor();
    if (!/^\s/.test(constructor)) {
        let constructorArray = constructor.split(/\n/);
        var newConstructorArray = [];
        constructorArray.forEach(function (element) {
            newConstructorArray.push("\t" + element);
        });
        constructor = newConstructorArray.join("\n");
    }
    // Generate the class declaration and constructor snippet
    // prettier-ignore
    const finalText = `\
${imports}
${jsonSerializableCombinedText}
${classNameLine}
${variables}

${constructor}

\tfactory ${className}.fromJson(Map<String, dynamic> json) =>
\t\t\t_$${className}FromJson(json);
\tMap<String, dynamic> toJson() => _$${className}ToJson(this);
}
	`;
    // Create a new TextEdit to replace the entire document content
    overwriteDocument(document, finalText);
}
function quickFixJsonSerializable(document, range) {
    // Get the current line where the cursor is positioned
    const lineIndex = range.start.line;
    const lineText = document.lineAt(lineIndex).text;
    const classRegex = lineText.match(/class\s+(\w+)/);
    const fileUri = document.uri;
    const fileName = path.basename(fileUri.fsPath, path.extname(fileUri.fsPath));
    let jsonSerializableHeaderImport = "import 'package:json_annotation/json_annotation.dart';";
    let jsonSerializableHeaderPart = `part '${fileName}.g.dart';`;
    let jsonSerializableHeaderNotation = "@JsonSerializable()";
    let textBeforeClass = "";
    if (range.start.line > 0) {
        const currentPosition = range.start;
        const lineNumber = currentPosition.line;
        const fullText = document.getText();
        const lines = fullText.split("\n");
        textBeforeClass = lines.slice(0, lineNumber).join("\n").trim();
    }
    // prettier-ignore
    textBeforeClass = `\
${textBeforeClass}
${textBeforeClass.includes(jsonSerializableHeaderImport) ? "" : `${jsonSerializableHeaderImport}\n`}\
${textBeforeClass.includes(jsonSerializableHeaderPart) ? "" : `${jsonSerializableHeaderPart}\n`}\
${textBeforeClass.includes(jsonSerializableHeaderNotation) ? "" : `\n${jsonSerializableHeaderNotation}\n`}\
  `;
    if (classRegex && fileName) {
        const className = classRegex[1];
        const variablesAvailable = getVariableMatchesFromClass(document.getText());
        let variableSection = "";
        let constructorVariableSection = "";
        for (const variable of variablesAvailable) {
            const variableName = variable.at(-1)?.trim() ?? "";
            const variableType = variable.at(-2)?.trim() ?? "";
            const variableConstFinal = variable.at(-3)?.trim() ?? "";
            const variableLate = variable.at(-4)?.trim() ?? "";
            // prettier-ignore
            variableSection += `\t${variableLate ? variableLate + " " : ""}${variableConstFinal ? variableConstFinal + " " : ""}${variableType ? variableType + " " : ""}${variableName};\n`;
            // prettier-ignore
            constructorVariableSection += `\n\t\t${variableType.includes("?") ? "" : "required "}this.${variableName},`;
        }
        // Generate the class declaration and constructor snippet
        // prettier-ignore
        const classSnippet = `\
${textBeforeClass}\
class ${className} {${variableSection.length === 0 ? "" : "\n"}${variableSection}
\t${className}(${constructorVariableSection.length === 0 ? "" : "{"}${constructorVariableSection}${constructorVariableSection.length === 0 ? "" : "\n\t"}${constructorVariableSection.length === 0 ? "" : "}"});

\tfactory ${className}.fromJson(Map<String, dynamic> json) =>
\t\t\t_$${className}FromJson(json);
\tMap<String, dynamic> toJson() => _$${className}ToJson(this);
}
	`;
        // Create a new TextEdit to replace the entire document content
        overwriteDocument(document, classSnippet);
    }
}
function getVariableMatchesFromClass(text) {
    // Regular expression to match class variables
    const regex = /(late\s+)?(final\s+|const\s+)?([\w\d_?]+)\s+([\w\d_]+);/gm;
    // Match all class variables
    const matches = text.matchAll(regex);
    return matches;
}
function overwriteDocument(document, newString) {
    let edit = new vscode.WorkspaceEdit();
    const wholeDocument = new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));
    edit.replace(document.uri, wholeDocument, newString);
    // Apply the edit to the document
    vscode.workspace.applyEdit(edit);
}
//# sourceMappingURL=extension.js.map