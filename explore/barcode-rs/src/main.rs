//! Command line front end.
//!
//! ```text
//!   jtq-barcode encode ORD-101 [--svg ticket.svg] [--module 2] [--height 60]
//!   jtq-barcode decode 2112141231221232212...      widths, as digits
//!   jtq-barcode check  ORD-101                     encode then decode, and diff
//! ```

use std::process::ExitCode;

use jtq_barcode::{bits, decode, encode_b, parse_widths, to_svg, widths};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        usage();
        return ExitCode::from(2);
    }

    match args[0].as_str() {
        "encode" => cmd_encode(&args[1..]),
        "decode" => cmd_decode(&args[1..]),
        "check" => cmd_check(&args[1..]),
        other => {
            eprintln!("unknown command: {other}\n");
            usage();
            ExitCode::from(2)
        }
    }
}

fn usage() {
    eprintln!(
        "Code 128 (subset B) for order tickets.\n\n\
           encode <data> [--svg <file>] [--module <px>] [--height <px>]\n\
               Encode and report the symbols; optionally write an SVG.\n\n\
           decode <width digits>\n\
             Read a barcode back from its element widths, checking the\n\
             modulo-103 check symbol.\n\n\
           check <data>\n\
             Encode then decode, and confirm the two agree."
    );
}

fn flag<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    let i = args.iter().position(|a| a == name)?;
    args.get(i + 1).map(|s| s.as_str())
}

fn cmd_encode(args: &[String]) -> ExitCode {
    let Some(data) = args.first() else {
        eprintln!("encode needs something to encode");
        return ExitCode::from(2);
    };

    let values = match encode_b(data) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("cannot encode: {e}");
            return ExitCode::from(1);
        }
    };

    let w = widths(&values);
    println!("data          : {data}");
    println!("symbols       : {values:?}");
    println!("check symbol  : {}", values.last().unwrap());
    println!("elements      : {}", w.len());
    println!("modules       : {}", w.iter().map(|x| *x as u32).sum::<u32>());
    println!("widths        : {}", w.iter().map(|x| x.to_string()).collect::<String>());
    println!("bits          : {}", bits(&w));

    if let Some(path) = flag(args, "--svg") {
        let module: f64 = flag(args, "--module").and_then(|s| s.parse().ok()).unwrap_or(2.0);
        let height: f64 = flag(args, "--height").and_then(|s| s.parse().ok()).unwrap_or(60.0);
        let svg = to_svg(data, &values, module, height);
        match std::fs::write(path, svg) {
            Ok(()) => println!("svg           : {path}"),
            Err(e) => {
                eprintln!("could not write {path}: {e}");
                return ExitCode::from(1);
            }
        }
    }
    ExitCode::SUCCESS
}

fn cmd_decode(args: &[String]) -> ExitCode {
    let Some(text) = args.first() else {
        eprintln!("decode needs a run of width digits");
        return ExitCode::from(2);
    };
    let w = parse_widths(text);
    match decode(&w) {
        Ok(data) => {
            println!("decoded       : {data}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            println!("REJECTED      : {e}");
            println!();
            println!("A scanner does the same thing. It does not read part of a");
            println!("barcode and guess the rest.");
            ExitCode::from(1)
        }
    }
}

fn cmd_check(args: &[String]) -> ExitCode {
    let Some(data) = args.first() else {
        eprintln!("check needs something to encode");
        return ExitCode::from(2);
    };
    let values = match encode_b(data) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("cannot encode: {e}");
            return ExitCode::from(1);
        }
    };
    match decode(&widths(&values)) {
        Ok(back) if back == *data => {
            println!("round trip OK : {data:?} -> {} symbols -> {back:?}", values.len());
            ExitCode::SUCCESS
        }
        Ok(back) => {
            println!("MISMATCH      : encoded {data:?} but decoded {back:?}");
            ExitCode::from(1)
        }
        Err(e) => {
            println!("MISMATCH      : encoded {data:?} but it would not decode: {e}");
            ExitCode::from(1)
        }
    }
}
