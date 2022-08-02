mod plugins;

fn main() {
    println!("Hello, world!");
}

#[cfg(test)]
mod tests {
    #[test]
    fn here_i_am() {
        println!("file test: main.rs");
    }
}
