use std::ops::Deref;
use std::path::Path;
use shellexpand;
use path_absolutize::Absolutize;
use chrono::{Utc, DateTime, FixedOffset, ParseError};

// ---------------------------------------------------------------------------
// get_absolute_path:
// ---------------------------------------------------------------------------
/** Replace tilde (~) and environment variable values in a path name and
 * then construct the absolute path name.  The difference between 
 * absolutize and standard canonicalize methods is that absolutize does not 
 * care about whether the file exists and what the file really is.
 * 
 * Here's a short version of how canonicalize would be used: 
 * 
 *   let p = shellexpand::full(path).unwrap();
 *   fs::canonicalize(p.deref()).unwrap().into_os_string().into_string().unwrap()
 * 
 * We have the option of using these to two ways to generate a String from the
 * input path (&str):
 * 
 *   path.to_owned()
 *   path.deref().to_string()
 * 
 * I went with the former on a hunch that it's the most appropriate, happy
 * to change if my guess is wrong.
 */
pub fn get_absolute_path(path: &str) -> String {
    // Replace ~ and environment variable values if possible.
    // On error, return the string version of the original path.
    let s = match shellexpand::full(path) {
        Ok(x) => x,
        Err(_) => return path.to_owned(),
    };

    // Convert to absolute path if necessary.
    // Return original input on error.
    let p = Path::new(s.deref());
    let p1 = match p.absolutize() {
        Ok(x) => x,
        Err(_) => return path.to_owned(),
    };
    let p2 = match p1.to_str() {
        Some(x) => x,
        None => return path.to_owned(),
    };

    p2.to_owned()
}

// ---------------------------------------------------------------------------
// timestamp_str:
// ---------------------------------------------------------------------------
/** Get the current UTC timestamp as a string in rfc3339 format, which looks
 * like this:  2022-09-13T14:14:42.719849912+00:00
 */
pub fn timestamp_str() -> String {
    Utc::now().to_rfc3339()
}

// ---------------------------------------------------------------------------
// timestamp_str_to_datetime:
// ---------------------------------------------------------------------------
/** Convert a timestamp string in rfc3339 format (ex: 2022-09-13T14:14:42.719849912+00:00)
 * to a DateTime object.  The result will contain a parse error if the string
 * does not conform to rfc3339.
 */
pub fn timestamp_str_to_datetime(ts: &String) -> Result<DateTime<FixedOffset>, ParseError> {
    DateTime::parse_from_rfc3339(ts)
}

mod tests {
    use crate::traps_utils::*;

    #[test]
    fn here_i_am() {
        println!("file test: traps_utils.rs");

        // Test timestamp string inversion: string to datetime back to string
        let s1 = timestamp_str();
        println!("current utc timestamp: {}", s1);
        let ts1 = timestamp_str_to_datetime(&s1).unwrap();
        let s2 = ts1.to_rfc3339();
        assert_eq!(s1, s2);
    }
}