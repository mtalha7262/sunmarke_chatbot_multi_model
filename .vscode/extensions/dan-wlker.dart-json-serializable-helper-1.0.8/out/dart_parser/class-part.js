"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ClassPart = void 0;
const vscode = require("vscode");
class ClassPart {
    constructor(name, startsAt = null, endsAt = null, current = null, replacement = null) {
        this.name = name;
        this.startsAt = startsAt;
        this.endsAt = endsAt;
        this.current = current;
        this.replacement = replacement;
    }
    get isValid() {
        return (this.startsAt !== null && this.endsAt !== null && this.current !== null);
    }
    get startPos() {
        if (this.startsAt === null) {
            throw new Error("startsAt is null for ClassPart");
        }
        return new vscode.Position(this.startsAt, 0);
    }
    get endPos() {
        if (this.endsAt === null) {
            throw new Error("endsAt is null for ClassPart");
        }
        return new vscode.Position(this.endsAt, 0);
    }
}
exports.ClassPart = ClassPart;
//# sourceMappingURL=class-part.js.map