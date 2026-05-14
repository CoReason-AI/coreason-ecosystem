use std::path::PathBuf;

fn main() {
    let mut p = PathBuf::from("/home/user/work/coreason-ecosystem/bootstrapper/src-tauri");
    p.push("../../infrastructure/local/compose.yaml");
    println!("{:?}", p);
}
