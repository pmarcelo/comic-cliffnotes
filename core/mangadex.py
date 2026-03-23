import argparse
from core import helpers

def build_metadata(manga_id: str, manga_title: str, target_chapter: float):
    print(f"📚 Fetching feeds for Chapter {target_chapter}...")
    full_map = helpers.fetch_chapter_map(manga_id)
    
    # Filter only the chapter we care about
    filtered_map = {str(k): v for k, v in full_map.items() if k == target_chapter}
    
    return {
        "manga_title": manga_title,
        "manga_id": manga_id,
        "target_chapter": target_chapter,
        "chapter_map": filtered_map
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-c", "--chapter", type=float, required=True)
    args = parser.parse_args()

    print(f"🔍 Searching for manga: '{args.title}'...")
    m_id, m_title = helpers.fetch_manga_id_and_title(args.title)
    
    if m_id:
        print(f"✅ Resolved Title: {m_title} (ID: {m_id})")
        metadata = build_metadata(m_id, m_title, args.chapter)
        
        if metadata["chapter_map"]:
            paths = helpers.get_paths(m_title, str(args.chapter))
            helpers.save_json(metadata, paths["metadata"])
            print(f"💾 Metadata successfully saved to: {paths['metadata']}")
        else:
            print(f"❌ Chapter {args.chapter} not found.")
    else:
        print("❌ Manga not found.")