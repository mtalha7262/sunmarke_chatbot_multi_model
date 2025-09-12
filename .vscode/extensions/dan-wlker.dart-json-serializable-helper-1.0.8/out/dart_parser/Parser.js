"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Parser = void 0;
const tokenizer_1 = require("./tokenizer");
class Parser {
    constructor() {
        this._string = "";
        this._tokenizer = new tokenizer_1.Tokenizer();
    }
    // parses string into AST
    parse(string) {
        this._string = string;
        this._tokenizer.init(string);
        // Prime the tokenizer to obtain the first token
        // which is our lookahead. The lookahead is used
        // for predective parsing.
        this._lookahead = this._tokenizer.getNextToken();
        // Parse recursively starting from the main entry
        // point, the Program
        return this.Program();
    }
    // eslint-disable-next-line @typescript-eslint/naming-convention
    Program() {
        return {
            type: "Program",
            body: this.NumericLiteral(),
        };
    }
    // eslint-disable-next-line @typescript-eslint/naming-convention
    NumericLiteral() {
        const token = this._eat("NUMBER");
        return {
            type: "NumericLiteral",
            value: Number(token.value),
        };
    }
    _eat(tokenType) {
        const token = this._lookahead;
        if (token === null || token === undefined) {
            throw new SyntaxError(`Unexpected end of input, expected "${tokenType}"`);
        }
        if (token.type !== tokenType) {
            throw new SyntaxError(`Unexpected token: "${token.value}", expected: "${tokenType}"`);
        }
        this._lookahead = this._tokenizer.getNextToken();
        return token;
    }
}
exports.Parser = Parser;
//# sourceMappingURL=parser.js.map