import requests

def find_bureaus_with_chief(agency_code):
    base_url = f"https://api.usaspending.gov/api/v2/agency/{agency_code}/sub_components/"
    page = 1
    matches = []

    while True:
        params = {'page': page}
        response = requests.get(base_url, params=params)
        print(response.url)
        response.raise_for_status()
        data = response.json()
        bureaus = data.get('results', [])

        for bureau in bureaus:
            # Adjust the field name if it's not 'name'
            name = bureau.get('name', '')
            print(name)
            if 'chief' in name.lower():
                matches.append(bureau)

        # Pagination logic: adjust if the API uses a different field
        if not data['page_metadata']['hasNext']:
            break
        page += 1

    return matches

# Example usage:
agency_code = "097"  # Replace with the desired top-tier agency code
chief_bureaus = find_bureaus_with_chief(agency_code)
for bureau in chief_bureaus:
    print(bureau)
