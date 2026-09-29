package jtq;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A small JSON reader and writer, so this tool has no dependencies to install.
 *
 * <p>The JDK still ships no JSON support, which is the one place Java makes
 * you work harder than Python for a command line tool. 180 lines buys back
 * the interchange format, and keeps the build a single {@code javac} call.
 *
 * <p>Values come back as the obvious Java types: {@code Map<String,Object>},
 * {@code List<Object>}, {@code String}, {@code Double}, {@code Boolean},
 * {@code null}.
 */
public final class Json {

    private final String src;
    private int pos;

    private Json(String src) {
        this.src = src;
    }

    public static Object parse(String text) {
        Json p = new Json(text);
        p.skipWhitespace();
        Object value = p.readValue();
        p.skipWhitespace();
        if (p.pos < p.src.length()) {
            throw p.error("trailing content after the top-level value");
        }
        return value;
    }

    // ---- reading ---------------------------------------------------------

    private Object readValue() {
        if (pos >= src.length()) throw error("unexpected end of input");
        char c = src.charAt(pos);
        return switch (c) {
            case '{' -> readObject();
            case '[' -> readArray();
            case '"' -> readString();
            case 't', 'f' -> readBoolean();
            case 'n' -> readNull();
            default -> readNumber();
        };
    }

    private Map<String, Object> readObject() {
        Map<String, Object> out = new LinkedHashMap<>();
        expect('{');
        skipWhitespace();
        if (peek() == '}') { pos++; return out; }
        while (true) {
            skipWhitespace();
            String key = readString();
            skipWhitespace();
            expect(':');
            skipWhitespace();
            out.put(key, readValue());
            skipWhitespace();
            char c = next();
            if (c == '}') return out;
            if (c != ',') throw error("expected ',' or '}' in object, got '" + c + "'");
        }
    }

    private List<Object> readArray() {
        List<Object> out = new ArrayList<>();
        expect('[');
        skipWhitespace();
        if (peek() == ']') { pos++; return out; }
        while (true) {
            skipWhitespace();
            out.add(readValue());
            skipWhitespace();
            char c = next();
            if (c == ']') return out;
            if (c != ',') throw error("expected ',' or ']' in array, got '" + c + "'");
        }
    }

    private String readString() {
        expect('"');
        StringBuilder sb = new StringBuilder();
        while (true) {
            if (pos >= src.length()) throw error("unterminated string");
            char c = src.charAt(pos++);
            if (c == '"') return sb.toString();
            if (c != '\\') { sb.append(c); continue; }
            char esc = next();
            switch (esc) {
                case '"', '\\', '/' -> sb.append(esc);
                case 'b' -> sb.append('\b');
                case 'f' -> sb.append('\f');
                case 'n' -> sb.append('\n');
                case 'r' -> sb.append('\r');
                case 't' -> sb.append('\t');
                case 'u' -> {
                    if (pos + 4 > src.length()) throw error("truncated \\u escape");
                    sb.append((char) Integer.parseInt(src.substring(pos, pos + 4), 16));
                    pos += 4;
                }
                default -> throw error("unknown escape \\" + esc);
            }
        }
    }

    private Boolean readBoolean() {
        if (src.startsWith("true", pos)) { pos += 4; return Boolean.TRUE; }
        if (src.startsWith("false", pos)) { pos += 5; return Boolean.FALSE; }
        throw error("expected true or false");
    }

    private Object readNull() {
        if (src.startsWith("null", pos)) { pos += 4; return null; }
        throw error("expected null");
    }

    private Double readNumber() {
        int start = pos;
        if (peek() == '-' || peek() == '+') pos++;
        while (pos < src.length() && "0123456789.eE+-".indexOf(src.charAt(pos)) >= 0) pos++;
        String text = src.substring(start, pos);
        if (text.isEmpty()) throw error("expected a value");
        try {
            return Double.valueOf(text);
        } catch (NumberFormatException e) {
            throw error("bad number: " + text);
        }
    }

    private void skipWhitespace() {
        while (pos < src.length() && Character.isWhitespace(src.charAt(pos))) pos++;
    }

    private char peek() {
        return pos < src.length() ? src.charAt(pos) : '\0';
    }

    private char next() {
        if (pos >= src.length()) throw error("unexpected end of input");
        return src.charAt(pos++);
    }

    private void expect(char c) {
        if (next() != c) throw error("expected '" + c + "'");
    }

    private IllegalArgumentException error(String message) {
        int line = 1;
        for (int i = 0; i < Math.min(pos, src.length()); i++) {
            if (src.charAt(i) == '\n') line++;
        }
        return new IllegalArgumentException("JSON line " + line + ": " + message);
    }

    // ---- writing ---------------------------------------------------------

    public static String write(Object value) {
        StringBuilder sb = new StringBuilder();
        writeInto(sb, value, 0);
        return sb.toString();
    }

    private static void writeInto(StringBuilder sb, Object value, int depth) {
        switch (value) {
            case null -> sb.append("null");
            case String s -> writeString(sb, s);
            case Boolean b -> sb.append(b);
            case Double d -> sb.append(compact(d));
            case Number n -> sb.append(compact(n.doubleValue()));
            case Map<?, ?> map -> {
                if (map.isEmpty()) { sb.append("{}"); return; }
                sb.append("{\n");
                int i = 0;
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    indent(sb, depth + 1);
                    writeString(sb, String.valueOf(e.getKey()));
                    sb.append(": ");
                    writeInto(sb, e.getValue(), depth + 1);
                    if (++i < map.size()) sb.append(',');
                    sb.append('\n');
                }
                indent(sb, depth);
                sb.append('}');
            }
            case List<?> list -> {
                if (list.isEmpty()) { sb.append("[]"); return; }
                sb.append("[\n");
                for (int i = 0; i < list.size(); i++) {
                    indent(sb, depth + 1);
                    writeInto(sb, list.get(i), depth + 1);
                    if (i < list.size() - 1) sb.append(',');
                    sb.append('\n');
                }
                indent(sb, depth);
                sb.append(']');
            }
            default -> writeString(sb, String.valueOf(value));
        }
    }

    /** Whole numbers print as 3, not 3.0 -- this output is read by people. */
    private static String compact(double d) {
        if (d == Math.rint(d) && !Double.isInfinite(d) && Math.abs(d) < 1e15) {
            return String.valueOf((long) d);
        }
        return String.valueOf(Math.round(d * 100.0) / 100.0);
    }

    private static void indent(StringBuilder sb, int depth) {
        sb.append("  ".repeat(depth));
    }

    private static void writeString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
                }
            }
        }
        sb.append('"');
    }
}
