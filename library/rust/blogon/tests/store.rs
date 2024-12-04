use blogon::store::Store;
use std::path::PathBuf;

fn setup() {
    let _ = env_logger::builder().is_test(true).try_init();
}

#[test]
fn get_post_by_slug() {
    setup();

    let store = Store::open(PathBuf::from("tests/data/posts"));
    let post = store.get_post_by_slug("1-toc").unwrap();
    assert_eq!(5, post.toc.len());
    assert_eq!([1u16, 0, 0, 0, 0, 0], post.toc[0].path);
    assert_eq!([1u16, 1, 0, 0, 0, 0], post.toc[1].path);
    assert_eq!([1u16, 1, 0, 1, 0, 0], post.toc[2].path);
    assert_eq!([1u16, 1, 1, 0, 0, 0], post.toc[3].path);
    assert_eq!([1u16, 2, 0, 0, 0, 0], post.toc[4].path);
}
