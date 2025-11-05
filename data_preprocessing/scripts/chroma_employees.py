import re
from bs4 import BeautifulSoup
import re
import demjson3
from urllib.parse import urljoin
import requests
import pandas as pd


FH_SCRAPE_URL = "https://www.fh-swf.de/de/ueber_uns/beschaeftigte_1/lehrende/index.php"



def collect_employee_information():
    employees_dict = []

    response = requests.get(FH_SCRAPE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    script = soup.find("script", id="course-data")

    match = re.search(
        r'window\.COURSE_APP_DATA\s*=\s*(\[.*?\]);',
        script.string,
        re.DOTALL
    )

    if not match:
        raise ValueError("window.COURSE_APP_DATA JSON-Objekt konnte nicht extrahiert werden")

    raw_json_str = match.group(1)

    # Lade JSON
    data = demjson3.decode(raw_json_str)

    data = data[0]

    for i, course in enumerate(data['courses']):
        employee_url = urljoin(FH_SCRAPE_URL, course["link"])

        response = requests.get(employee_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        aside = soup.find("aside")
        if i % 20 == 0:
            print(i)
        if aside:
            # Standort
            location_span = aside.find("span", class_="f-weight--700")
            location = location_span.get_text(strip=True) if location_span else None

            # Name
            h3 = aside.find("div", class_="headline--3")
            name_title = h3.get_text(strip=True) if h3 else None
            if not name_title:
                continue

            # Telefonnummer
            phone = None
            tel_a = aside.find("a", href=lambda x: x and x.startswith("tel:"))
            if tel_a:
                phone = tel_a.get_text(strip=True)

            # E-Mail
            email = None
            email_a = aside.find("a", href=lambda x: x and x.startswith("mailto:"))
            if email_a:
                email = email_a.get_text(strip=True)

            # Adresse
            address_div = aside.find("div", class_="headline--4", string="Hausanschrift")
            address = None
            if address_div:
                address_p = address_div.find_next_sibling("p")
                if address_p:
                    address = address_p.get_text(separator=" ", strip=True)

            employees_dict.append({"Name": name_title, "Standort": location, "Telefon": phone, "E-Mail": email, "Homepage": employee_url, "Adresse": address})
        else:
            print("Kein passender <aside>-Block gefunden.")

    pd.DataFrame(employees_dict).to_csv("mitarbeiter.csv", index=False)


if __name__ == "__main__":
    collect_employee_information()


