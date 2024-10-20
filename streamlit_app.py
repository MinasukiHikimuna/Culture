import streamlit as st
import pandas as pd
from libraries.client_stashapp import get_stashapp_client
import dotenv

def fetch_data():
    dotenv.load_dotenv()
    stash = get_stashapp_client()

    def create_modified_filter(data_quality_filter):
        if 'tags' not in data_quality_filter['object_filter']:
            print(f"Warning: 'tags' not found in object_filter for filter: {data_quality_filter['name']}")
            return None

        depth = data_quality_filter['object_filter']['tags']['value']['depth']
        included_tag_ids = [tag['id'] for tag in data_quality_filter['object_filter']['tags']['value']['items']]
        excluded_tag_ids = [tag['id'] for tag in data_quality_filter['object_filter']['tags']['value']['excluded']]

        return {
            'tags': {
                'modifier': 'INCLUDES_ALL',
                'value': included_tag_ids,
                'depth': depth,
                'excludes': excluded_tag_ids,
            }
        }

    def get_scene_count(filter):
        result = stash.call_GQL("""query FindScenes($scene_filter: SceneFilterType) {
            findScenes(scene_filter: $scene_filter) {
                count
            }
        }""", variables={"scene_filter": filter})
        return result['findScenes']['count']

    saved_filters = stash.call_GQL("""query FindSavedFilters {
        findSavedFilters {
            id
            mode
            name
            filter
            object_filter
            ui_options
        }
    }""")

    data_quality_filters = [filter for filter in saved_filters['findSavedFilters'] if 'data quality' in filter['name'].lower()]
    sorted_data_quality_filters = sorted(data_quality_filters, key=lambda x: x['name'])

    metrics = []
    for filter in sorted_data_quality_filters:
        name = filter['name']
        modified_filter = create_modified_filter(filter)
        if modified_filter is not None:
            scene_count = get_scene_count(modified_filter)
            metrics.append({
                "metricName": name,
                "itemCount": scene_count,
                "sourceLink": f"http://localhost:6969/scenes?c={filter['id']}"
            })

    return metrics

def main():
    st.title("Data Quality Metrics Dashboard")
    
    data = fetch_data()
    if data:
        df = pd.DataFrame(data)
        
        # Create a new column with clickable links
        df['Metric'] = df.apply(
            lambda row: f"<a href='{row['sourceLink']}' target='_blank'>{row['metricName']}</a>", axis=1
        )
        
        # Select the columns to display
        display_df = df[['Metric', 'itemCount']]
        display_df.rename(columns={'itemCount': 'Number of Issues'}, inplace=True)
        
        # Display the table with HTML rendering
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No data available.")

if __name__ == "__main__":
    main()
