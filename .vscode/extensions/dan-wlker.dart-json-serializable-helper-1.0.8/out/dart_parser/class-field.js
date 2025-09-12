"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ClassField = void 0;
const utils_1 = require("./utils");
class ClassField {
    constructor(type, name, line = 1, isFinal = true, isConst = false) {
        this.rawType = type;
        this.jsonName = name;
        this.name = (0, utils_1.toVarName)(name);
        this.line = line;
        this.isFinal = isFinal;
        this.isConst = isConst;
        this.isEnum = false;
        this.isCollectionType = (type) => this.rawType === type || (this?.rawType?.startsWith(type + "<") ?? false);
    }
    get type() {
        return this.isNullable ? (0, utils_1.removeEnd)(this.rawType, "?") : this.rawType;
    }
    get isNullable() {
        return this.rawType.endsWith("?");
    }
    get isList() {
        return this.isCollectionType("List");
    }
    get isMap() {
        return this.isCollectionType("Map");
    }
    get isSet() {
        return this.isCollectionType("Set");
    }
    get isCollection() {
        return this.isList || this.isMap || this.isSet;
    }
    get listType() {
        if (this.isList || this.isSet) {
            const collection = this.isSet ? "Set" : "List";
            const type = this.rawType === collection
                ? "dynamic"
                : this.rawType.replace(collection + "<", "").replace(">", "");
            return new ClassField(type, this.name, this.line, this.isFinal);
        }
        return this;
    }
    get isPrimitive() {
        let t = this.listType.type;
        return (t === "String" ||
            t === "num" ||
            t === "dynamic" ||
            t === "bool" ||
            this.isDouble ||
            this.isInt ||
            this.isMap);
    }
    get isPrivate() {
        return this.name.startsWith("_");
    }
    get defValue() {
        if (this.isList) {
            return "const []";
        }
        else if (this.isMap || this.isSet) {
            return "const {}";
        }
        else {
            switch (this.type) {
                case "String":
                    return "''";
                case "num":
                case "int":
                    return "0";
                case "double":
                    return "0.0";
                case "bool":
                    return "false";
                case "dynamic":
                    return "null";
                default:
                    return `${this.type}()`;
            }
        }
    }
    get isInt() {
        return this.listType.type === "int";
    }
    get isDouble() {
        return this.listType.type === "double";
    }
}
exports.ClassField = ClassField;
//# sourceMappingURL=class-field.js.map