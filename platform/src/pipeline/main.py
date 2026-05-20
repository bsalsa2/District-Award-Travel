from platform.src.pipeline.search_pipeline import SearchPipeline
from platform.src.pipeline.db import create_database

def main():
    create_database("search_results.db")
    pipeline = SearchPipeline("search_results.db", 10)
    jobs = [SearchJob("NYC-LAX", "2026-05-20"), SearchJob("LAX-NYC", "2026-05-21")]
    pipeline.start(jobs)

if __name__ == "__main__":
    main()
