"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Tokenizer = void 0;
class Tokenizer {
    constructor() {
        this._string = "";
        this._cursor = 0;
    }
    init(string) {
        this._string = string;
        this._cursor = 0;
    }
    hasMoreTokens() {
        return this._cursor < this._string.length;
    }
    getNextToken() {
        if (!this.hasMoreTokens()) {
            return null;
        }
        const string = this._string.slice(this._cursor);
        if (!Number.isNaN(string[0])) {
            let number = "";
            while (!Number.isNaN(string[this._cursor])) {
                number += string[this._cursor++];
            }
            return {
                type: "NUMBER",
                value: number,
            };
        }
    }
}
exports.Tokenizer = Tokenizer;
//# sourceMappingURL=tokenizer.js.map