"""
Comprehensive company name to ticker mapping generator.

This module provides a unified mapping of company names (and common aliases) to ticker symbols.
It combines:
1. S&P 500 companies from the local CSV
2. Popular non-S&P 500 companies (NASDAQ, NYSE listed)
3. Common abbreviations and brand names
"""

from __future__ import annotations

import re
from functools import lru_cache

from .sp500 import load_sp500, _normalize, _strip_corp_suffixes, _SHORT_NAME_ALIASES


# Common short names for S&P 500 companies that might not be automatically extracted
# These are the most frequently used names in news articles
_COMMON_SHORT_NAMES: dict[str, list[str]] = {
    # Big Tech (FAANG/MAMAA)
    "AAPL": ["apple"],
    "MSFT": ["microsoft"],
    "GOOGL": ["google", "alphabet"],
    "GOOG": ["google", "alphabet"],
    "AMZN": ["amazon"],
    "META": ["meta", "facebook"],
    "NFLX": ["netflix"],
    "NVDA": ["nvidia", "jensen huang"],
    "TSLA": ["tesla", "elon musk"],
    # Other major tech
    "AMD": ["amd"],
    "INTC": ["intel"],
    "CSCO": ["cisco"],
    "ORCL": ["oracle"],
    "CRM": ["salesforce"],
    "ADBE": ["adobe"],
    "IBM": ["ibm"],
    "INTU": ["intuit", "turbotax"],
    "NOW": ["servicenow"],
    "AVGO": ["broadcom"],
    "QCOM": ["qualcomm"],
    "TXN": ["texas instruments"],
    # Major banks
    "JPM": ["jpmorgan", "jp morgan", "chase", "jamie dimon"],
    "BAC": ["bank of america", "bofa"],
    "WFC": ["wells fargo"],
    "C": ["citigroup", "citi", "citibank"],
    "GS": ["goldman sachs", "goldman"],
    "MS": ["morgan stanley"],
    # Consumer
    "WMT": ["walmart"],
    "COST": ["costco"],
    "HD": ["home depot"],
    "TGT": ["target"],
    "NKE": ["nike"],
    "SBUX": ["starbucks"],
    "MCD": ["mcdonalds", "mcdonald's"],
    "KO": ["coca-cola", "coca cola", "coke"],
    "PEP": ["pepsi", "pepsico"],
    "PG": ["procter & gamble", "procter gamble", "p&g"],
    # Healthcare
    "JNJ": ["johnson & johnson", "johnson and johnson", "j&j"],
    "PFE": ["pfizer"],
    "MRK": ["merck"],
    "ABBV": ["abbvie"],
    "LLY": ["eli lilly", "lilly"],
    "UNH": ["unitedhealth"],
    # Energy
    "XOM": ["exxon", "exxonmobil"],
    "CVX": ["chevron"],
    # Entertainment & Media
    "DIS": ["disney", "walt disney"],
    "CMCSA": ["comcast", "nbc", "nbcuniversal"],
    # Telecom
    "T": ["at&t", "att"],
    "VZ": ["verizon"],
    "TMUS": ["t-mobile", "tmobile"],
    # Payments
    "V": ["visa"],
    "MA": ["mastercard"],
    "PYPL": ["paypal"],
    # Auto
    "F": ["ford"],
    "GM": ["general motors"],
    # Fintech / Disruptors
    "SQ": ["square", "block", "cash app"],
    "COIN": ["coinbase"],
    "UBER": ["uber"],
    "ABNB": ["airbnb"],
    "PLTR": ["palantir"],
    "CRWD": ["crowdstrike"],
    # Defense
    "BA": ["boeing"],
    "LMT": ["lockheed martin", "lockheed"],
    "RTX": ["raytheon"],
    # Insurance
    "BRK-B": ["berkshire hathaway", "berkshire", "warren buffett"],
    # ETFs
    "SPY": ["s&p 500", "s&p500", "sp500"],
    "QQQ": ["nasdaq", "nasdaq 100"],
    "DIA": ["dow jones", "dow", "djia"],
}


# Additional companies not in S&P 500 but commonly mentioned in financial news
_EXTRA_COMPANIES: dict[str, list[str]] = {
    # Popular tech companies
    "RIVN": ["rivian"],
    "LCID": ["lucid", "lucid motors"],
    "NIO": ["nio"],
    "XPEV": ["xpeng"],
    "LI": ["li auto"],
    "SNOW": ["snowflake"],
    "DDOG": ["datadog"],
    "MDB": ["mongodb"],
    "TEAM": ["atlassian"],
    "TWLO": ["twilio"],
    "OKTA": ["okta"],
    "DOCU": ["docusign"],
    "ZM": ["zoom", "zoom video"],
    "ROKU": ["roku"],
    "SQ": ["square", "block"],
    "HOOD": ["robinhood"],
    "COIN": ["coinbase"],
    "SOFI": ["sofi"],
    "AFRM": ["affirm"],
    "UPST": ["upstart"],
    "PATH": ["uipath"],
    "U": ["unity", "unity software"],
    "RBLX": ["roblox"],
    "MTCH": ["match group", "tinder", "hinge"],
    "PINS": ["pinterest"],
    "SNAP": ["snap", "snapchat"],
    "X": ["twitter", "x corp"],  # Note: X is the new Twitter
    "RDDT": ["reddit"],
    "SPOT": ["spotify"],
    "SE": ["sea limited", "shopee", "garena"],
    "GRAB": ["grab"],
    "BABA": ["alibaba"],
    "JD": ["jd", "jd.com", "jingdong"],
    "PDD": ["pinduoduo", "pdd", "temu"],
    "BIDU": ["baidu"],
    "NTES": ["netease"],
    "BILI": ["bilibili"],
    "TME": ["tencent music"],
    "TCEHY": ["tencent"],
    "MELI": ["mercadolibre"],
    "NU": ["nubank"],
    "SHOP": ["shopify"],
    "TTD": ["trade desk"],
    "CRSP": ["crispr"],
    "EDIT": ["editas"],
    "NTLA": ["intellia"],
    "MRNA": ["moderna"],
    "BNTX": ["biontech"],
    "NVAX": ["novavax"],
    "ARKG": ["ark genomics"],
    "ARKK": ["ark innovation", "cathie wood"],
    "SPCE": ["virgin galactic"],
    "RKT": ["rocket companies", "rocket mortgage"],
    "OPEN": ["opendoor"],
    "Z": ["zillow"],
    "ZG": ["zillow group"],
    "CVNA": ["carvana"],
    "VRM": ["vroom"],
    "W": ["wayfair"],
    "ETSY": ["etsy"],
    "CHWY": ["chewy"],
    "PTON": ["peloton"],
    "FVRR": ["fiverr"],
    "UPWK": ["upwork"],
    "DASH": ["doordash"],
    "LYFT": ["lyft"],
    "GRAB": ["grab"],
    "CPNG": ["coupang"],
    "SE": ["sea limited"],
    "LULU": ["lululemon"],
    "NKE": ["nike"],
    "ADDYY": ["adidas"],
    "PUMA": ["puma"],
    "UA": ["under armour"],
    "VFC": ["vf corporation", "north face", "vans"],
    "RL": ["ralph lauren"],
    "LVMUY": ["lvmh"],
    "HESAY": ["hermes"],
    "CFRUY": ["richemont", "cartier"],
    "TIF": ["tiffany"],
    "SBUX": ["starbucks"],
    "DPZ": ["dominos", "domino's pizza"],
    "YUM": ["yum brands", "pizza hut", "taco bell", "kfc"],
    "QSR": ["restaurant brands", "burger king", "tim hortons", "popeyes"],
    "WEN": ["wendy's", "wendys"],
    "JACK": ["jack in the box"],
    "SHAK": ["shake shack"],
    "WING": ["wingstop"],
    "TXRH": ["texas roadhouse"],
    "EAT": ["brinker", "chili's", "chilis"],
    "DRI": ["darden", "olive garden", "longhorn"],
    "PLAY": ["dave and busters", "dave & busters"],
    "SIX": ["six flags"],
    "FUN": ["cedar fair"],
    "SEAS": ["seaworld"],
    "LVS": ["las vegas sands", "sands"],
    "WYNN": ["wynn"],
    "MGM": ["mgm resorts", "mgm"],
    "CZR": ["caesars"],
    "PENN": ["penn entertainment", "barstool"],
    "DKNG": ["draftkings"],
    "GNOG": ["golden nugget"],
    "RSI": ["rush street"],
    "SONY": ["sony"],
    "NTDOY": ["nintendo"],
    "ATVI": ["activision", "activision blizzard"],
    "RBLX": ["roblox"],
    "TTWO": ["take-two", "take two", "rockstar", "2k games"],
    "EA": ["electronic arts", "ea sports"],
    "ZNGA": ["zynga"],
    "GLBE": ["global-e"],
    "BILL": ["bill.com", "bill holdings"],
    "HUBS": ["hubspot"],
    "WDAY": ["workday"],
    "VEEV": ["veeva"],
    "SPLK": ["splunk"],
    "ESTC": ["elastic"],
    "CFLT": ["confluent"],
    "DBX": ["dropbox"],
    "BOX": ["box"],
    "ZEN": ["zendesk"],
    "FROG": ["jfrog"],
    "FSLY": ["fastly"],
    "AKAM": ["akamai"],
    "LLAP": ["terran orbital"],
    "ASTS": ["ast spacemobile"],
    "LUNR": ["intuitive machines"],
    "RKLB": ["rocket lab"],
    "ASTR": ["astra"],
    "MNTS": ["momentus"],
    "SPIR": ["spire global"],
    "ARM": ["arm holdings", "arm"],
    "SMCI": ["super micro", "supermicro"],
    "AI": ["c3.ai", "c3 ai"],
    "PLTR": ["palantir"],
    "S": ["sentinelone"],
    "CYBR": ["cyberark"],
    "CHKP": ["check point"],
    "MIME": ["mimecast"],
    "QLYS": ["qualys"],
    "RPD": ["rapid7"],
    "TENB": ["tenable"],
    "VMW": ["vmware"],
    "DELL": ["dell"],
    "HPQ": ["hp inc", "hp"],
    "HPE": ["hewlett packard enterprise"],
    "IBM": ["ibm"],
    "CSCO": ["cisco"],
    "JNPR": ["juniper"],
    "ANET": ["arista"],
    "FFIV": ["f5"],
    "CIEN": ["ciena"],
    "GLW": ["corning"],
    "TEL": ["te connectivity"],
    "APH": ["amphenol"],
    "KEYS": ["keysight"],
    "ANSS": ["ansys"],
    "PTC": ["ptc"],
    "ADSK": ["autodesk"],
    "MANH": ["manhattan associates"],
    "SSNC": ["ss&c"],
    "JKHY": ["jack henry"],
    "FIS": ["fis"],
    "FISV": ["fiserv"],
    "GPN": ["global payments"],
    "FLT": ["fleetcor"],
    "WU": ["western union"],
    "PYPL": ["paypal"],
    "SQ": ["square", "block", "cash app"],
    "AFRM": ["affirm"],
    "UPST": ["upstart"],
    "LC": ["lendingclub"],
    "TREE": ["lendingtree"],
    "INTU": ["intuit", "turbotax", "quickbooks"],
    "HRB": ["h&r block"],
    "WEX": ["wex"],
    "LPRO": ["open lending"],
    "UWMC": ["uwm holdings"],
    "GHLD": ["guild holdings"],
    "RKT": ["rocket companies", "rocket mortgage", "quicken loans"],
    "CSGP": ["costar"],
    "RDFN": ["redfin"],
    "ZG": ["zillow group"],
    "REAL": ["realreal"],
    "COMP": ["compass"],
    "EXPE": ["expedia"],
    "TRIP": ["tripadvisor"],
    "BKNG": ["booking", "booking.com", "priceline", "kayak"],
    "ABNB": ["airbnb"],
    "MAR": ["marriott"],
    "H": ["hyatt"],
    "IHG": ["intercontinental hotels", "ihg"],
    "CHH": ["choice hotels"],
    "WH": ["wyndham"],
    "HGV": ["hilton grand vacations"],
    "TNL": ["travel + leisure"],
    "PLYA": ["playa hotels"],
    "PK": ["park hotels"],
    "HST": ["host hotels"],
    "XHR": ["xenia hotels"],
    "SHO": ["sunstone"],
    "RLJ": ["rlj lodging"],
    "CLDT": ["chatham lodging"],
    "DRH": ["diamondrock"],
    "AHT": ["ashford hospitality"],
    "SVC": ["service properties"],
    "AAL": ["american airlines"],
    "DAL": ["delta airlines", "delta"],
    "UAL": ["united airlines", "united"],
    "LUV": ["southwest airlines", "southwest"],
    "ALK": ["alaska airlines", "alaska air"],
    "JBLU": ["jetblue"],
    "SAVE": ["spirit airlines", "spirit"],
    "ULCC": ["frontier airlines", "frontier"],
    "HA": ["hawaiian airlines", "hawaiian"],
    "SKYW": ["skywest"],
    "MESA": ["mesa airlines"],
    "ALGT": ["allegiant"],
    "RYAAY": ["ryanair"],
    "LHA": ["lufthansa"],
    "AF": ["air france"],
    "BA": ["boeing"],  # Also in S&P500
    "AIR": ["airbus"],
    "EADSY": ["airbus"],
    "ERJ": ["embraer"],
    "TXT": ["textron"],
    "GD": ["general dynamics"],
    "LMT": ["lockheed martin", "lockheed"],
    "NOC": ["northrop grumman", "northrop"],
    "RTX": ["raytheon", "rtx"],
    "HII": ["huntington ingalls"],
    "KTOS": ["kratos"],
    "RCAT": ["red cat"],
    "JOBY": ["joby aviation"],
    "EVTL": ["vertical aerospace"],
    "ACHR": ["archer aviation"],
    "LILM": ["lilium"],
    "BLDE": ["blade air mobility"],
    
    # Cryptocurrencies (for news articles)
    "BTC-USD": ["bitcoin", "btc"],
    "ETH-USD": ["ethereum", "eth"],
    "SOL-USD": ["solana", "sol"],
    "ADA-USD": ["cardano", "ada"],
    "DOGE-USD": ["dogecoin", "doge"],
    "XRP-USD": ["ripple", "xrp"],
    "DOT-USD": ["polkadot", "dot"],
    "AVAX-USD": ["avalanche", "avax"],
    "MATIC-USD": ["polygon", "matic"],
    "LINK-USD": ["chainlink", "link"],
    "UNI-USD": ["uniswap", "uni"],
    "ATOM-USD": ["cosmos", "atom"],
    "LTC-USD": ["litecoin", "ltc"],
    
    # Crypto stocks
    "MSTR": ["microstrategy", "michael saylor"],
    "MARA": ["marathon digital", "marathon holdings"],
    "RIOT": ["riot platforms", "riot blockchain"],
    "COIN": ["coinbase"],
    "HUT": ["hut 8"],
    "BITF": ["bitfarms"],
    "CIFR": ["cipher mining"],
    "CLSK": ["cleanspark"],
    
    # Electric vehicles & clean energy
    "TSLA": ["tesla", "elon musk"],
    "RIVN": ["rivian"],
    "LCID": ["lucid"],
    "FSR": ["fisker"],
    "FFIE": ["faraday future"],
    "GOEV": ["canoo"],
    "REE": ["ree automotive"],
    "ARVL": ["arrival"],
    "WKHS": ["workhorse"],
    "RIDE": ["lordstown"],
    "NKLA": ["nikola"],
    "HYLN": ["hyliion"],
    "BLNK": ["blink charging"],
    "CHPT": ["chargepoint"],
    "EVgo": ["evgo"],
    "VLTA": ["volta"],
    "QS": ["quantumscape"],
    "MVST": ["microvast"],
    "FREY": ["freyr battery"],
    "ENVX": ["enovix"],
    "PTRA": ["proterra"],
    "PLUG": ["plug power"],
    "FCEL": ["fuelcell energy"],
    "BE": ["bloom energy"],
    "BLDP": ["ballard power"],
    "ENPH": ["enphase"],
    "SEDG": ["solaredge"],
    "FSLR": ["first solar"],
    "SPWR": ["sunpower"],
    "RUN": ["sunrun"],
    "NOVA": ["sunnova"],
    "CSIQ": ["canadian solar"],
    "JKS": ["jinko solar"],
    "DQ": ["daqo new energy"],
    
    # Semiconductors
    "NVDA": ["nvidia", "jensen huang"],
    "AMD": ["amd", "advanced micro devices", "lisa su"],
    "INTC": ["intel"],
    "TSM": ["tsmc", "taiwan semiconductor"],
    "ASML": ["asml"],
    "LRCX": ["lam research", "lam"],
    "AMAT": ["applied materials"],
    "KLAC": ["kla corporation", "kla"],
    "MU": ["micron"],
    "MRVL": ["marvell"],
    "ON": ["onsemi", "on semiconductor"],
    "NXPI": ["nxp semiconductors", "nxp"],
    "STM": ["stmicroelectronics", "stmicro"],
    "TXN": ["texas instruments", "ti"],
    "ADI": ["analog devices"],
    "MCHP": ["microchip technology", "microchip"],
    "SWKS": ["skyworks"],
    "QRVO": ["qorvo"],
    "CRUS": ["cirrus logic"],
    "SLAB": ["silicon labs"],
    "MPWR": ["monolithic power"],
    "ALGM": ["allegro microsystems"],
    "WOLF": ["wolfspeed"],
    "ACLS": ["axcelis technologies"],
    "UCTT": ["ultra clean holdings"],
    "FORM": ["formfactor"],
    "CEVA": ["ceva"],
    "SIMO": ["silicon motion"],
    "AOSL": ["alpha and omega semiconductor"],
    
    # Banks and financial
    "JPM": ["jpmorgan", "jp morgan", "chase", "jamie dimon"],
    "BAC": ["bank of america", "bofa"],
    "WFC": ["wells fargo"],
    "C": ["citigroup", "citi", "citibank"],
    "GS": ["goldman sachs", "goldman"],
    "MS": ["morgan stanley"],
    "USB": ["us bancorp", "us bank"],
    "PNC": ["pnc"],
    "TFC": ["truist"],
    "SCHW": ["charles schwab", "schwab"],
    "BK": ["bank of new york", "bny mellon"],
    "STT": ["state street"],
    "NTRS": ["northern trust"],
    "KEY": ["keycorp", "keybank"],
    "CFG": ["citizens financial"],
    "RF": ["regions"],
    "FITB": ["fifth third"],
    "HBAN": ["huntington bancshares"],
    "ZION": ["zions bancorporation"],
    "CMA": ["comerica"],
    "MTB": ["m&t bank"],
    "ALLY": ["ally financial", "ally bank"],
    "COF": ["capital one"],
    "DFS": ["discover"],
    "SYF": ["synchrony"],
    "AXP": ["american express", "amex"],
    "V": ["visa"],
    "MA": ["mastercard"],
    "PYPL": ["paypal"],
    
    # Oil and gas
    "XOM": ["exxon", "exxonmobil", "exxon mobil"],
    "CVX": ["chevron"],
    "SHEL": ["shell", "royal dutch shell"],
    "BP": ["bp", "british petroleum"],
    "TTE": ["totalenergies", "total"],
    "COP": ["conocophillips"],
    "EOG": ["eog resources", "eog"],
    "PXD": ["pioneer natural resources", "pioneer"],
    "DVN": ["devon energy", "devon"],
    "OXY": ["occidental", "occidental petroleum"],
    "FANG": ["diamondback energy", "diamondback"],
    "HES": ["hess"],
    "MRO": ["marathon oil"],
    "APA": ["apache", "apa corporation"],
    "SLB": ["schlumberger"],
    "HAL": ["halliburton"],
    "BKR": ["baker hughes"],
    "NOV": ["nov"],
    "CLR": ["continental resources"],
    "OVV": ["ovintiv"],
    "CTRA": ["coterra"],
    "RRC": ["range resources"],
    "AR": ["antero resources"],
    "SWN": ["southwestern energy"],
    "EQT": ["eqt corporation"],
    "CHK": ["chesapeake energy"],
    "MTDR": ["matador resources"],
    "CPE": ["callon petroleum"],
    "SM": ["sm energy"],
    "PDCE": ["pdce energy"],
    "CHRD": ["chord energy"],
    
    # Healthcare and pharma
    "JNJ": ["johnson & johnson", "johnson and johnson", "j&j"],
    "PFE": ["pfizer"],
    "MRK": ["merck"],
    "ABBV": ["abbvie"],
    "LLY": ["eli lilly", "lilly"],
    "BMY": ["bristol myers squibb", "bristol-myers"],
    "AMGN": ["amgen"],
    "GILD": ["gilead"],
    "VRTX": ["vertex"],
    "REGN": ["regeneron"],
    "BIIB": ["biogen"],
    "MRNA": ["moderna"],
    "BNTX": ["biontech"],
    "AZN": ["astrazeneca"],
    "NVS": ["novartis"],
    "GSK": ["gsk", "glaxosmithkline"],
    "SNY": ["sanofi"],
    "NVO": ["novo nordisk"],
    "TAK": ["takeda"],
    "ALNY": ["alnylam"],
    "SGEN": ["seagen"],
    "BMRN": ["biomarin"],
    "INCY": ["incyte"],
    "EXEL": ["exelixis"],
    "SRPT": ["sarepta"],
    "UTHR": ["united therapeutics"],
    "BLUE": ["bluebird bio"],
    "RARE": ["ultragenyx"],
    "ALKS": ["alkermes"],
    "NBIX": ["neurocrine"],
    "JAZZ": ["jazz pharmaceuticals"],
    "HZNP": ["horizon therapeutics"],
    "IONS": ["ionis"],
    "BGNE": ["beigene"],
    "BPMC": ["blueprint medicines"],
    "PCVX": ["vaxcyte"],
    "ROIV": ["roivant"],
    "RXRX": ["recursion"],
    "DNA": ["ginkgo bioworks"],
    
    # Retail
    "WMT": ["walmart"],
    "AMZN": ["amazon"],
    "TGT": ["target"],
    "COST": ["costco"],
    "HD": ["home depot"],
    "LOW": ["lowes", "lowe's"],
    "BBBY": ["bed bath beyond"],
    "BBY": ["best buy"],
    "GME": ["gamestop"],
    "FIVE": ["five below"],
    "OLLI": ["ollies", "ollie's bargain outlet"],
    "BJ": ["bj's wholesale"],
    "DG": ["dollar general"],
    "DLTR": ["dollar tree"],
    "ROST": ["ross stores", "ross dress for less"],
    "TJX": ["tjx", "tj maxx", "marshalls"],
    "BURL": ["burlington"],
    "KSS": ["kohls", "kohl's"],
    "M": ["macy's", "macys"],
    "JWN": ["nordstrom"],
    "DDS": ["dillard's", "dillards"],
    "GPS": ["gap"],
    "ANF": ["abercrombie"],
    "AEO": ["american eagle"],
    "URBN": ["urban outfitters"],
    "EXPR": ["express"],
    "CATO": ["cato"],
    "SCVL": ["shoe carnival"],
    "FL": ["foot locker"],
    "DKS": ["dicks sporting goods", "dick's"],
    "HIBB": ["hibbett"],
    "BGFV": ["big 5"],
    "ASO": ["academy sports"],
    "ULTA": ["ulta beauty", "ulta"],
    "SFIX": ["stitch fix"],
    "RENT": ["rent the runway"],
    "LESL": ["leslie's"],
    "PRPL": ["purple innovation"],
    "LOVE": ["lovesac"],
    "ARHS": ["arhaus"],
    "RH": ["restoration hardware", "rh"],
    "WSM": ["williams-sonoma"],
    "BBWI": ["bath body works", "bath & body works"],
    "VSCO": ["victoria's secret"],
    
    # Food and beverage
    "KO": ["coca cola", "coca-cola", "coke"],
    "PEP": ["pepsi", "pepsico"],
    "MNST": ["monster beverage", "monster energy"],
    "KDP": ["keurig dr pepper"],
    "STZ": ["constellation brands", "corona", "modelo"],
    "BUD": ["anheuser busch", "budweiser", "ab inbev"],
    "TAP": ["molson coors"],
    "SAM": ["boston beer", "samuel adams"],
    "DEO": ["diageo", "johnnie walker", "guinness"],
    "BF.A": ["brown forman", "jack daniels"],
    "MKC": ["mccormick"],
    "HSY": ["hershey"],
    "MDLZ": ["mondelez", "oreo", "cadbury"],
    "K": ["kellanova", "kellogg"],
    "GIS": ["general mills", "cheerios"],
    "CAG": ["conagra"],
    "CPB": ["campbell soup", "campbell's"],
    "SJM": ["j.m. smucker", "smuckers"],
    "HRL": ["hormel"],
    "TSN": ["tyson foods", "tyson"],
    "PPC": ["pilgrim's pride"],
    "SAFM": ["sanderson farms"],
    "CALM": ["cal maine"],
    "KR": ["kroger"],
    "ACI": ["albertsons"],
    "SFM": ["sprouts"],
    "CASY": ["casey's"],
    "UNFI": ["united natural foods"],
    
    # Consumer products
    "PG": ["procter gamble", "procter & gamble", "p&g", "tide", "gillette"],
    "CL": ["colgate palmolive", "colgate"],
    "KMB": ["kimberly clark", "kleenex", "huggies"],
    "CHD": ["church dwight", "arm & hammer"],
    "CLX": ["clorox"],
    "EL": ["estee lauder"],
    "COTY": ["coty"],
    "IPAR": ["inter parfums"],
    "ELF": ["e.l.f. beauty", "elf cosmetics"],
    "SKIN": ["beauty health", "hydrafacial"],
    "NUS": ["nu skin"],
    "HIMS": ["hims & hers"],
    "OUST": ["ouster"],
    
    # Media and entertainment
    "DIS": ["disney", "walt disney"],
    "CMCSA": ["comcast", "nbcuniversal", "nbc"],
    "NFLX": ["netflix"],
    "WBD": ["warner bros discovery", "warner bros", "hbo", "discovery"],
    "PARA": ["paramount"],
    "FOX": ["fox", "fox news", "fox corp"],
    "FOXA": ["fox corporation"],
    "FWONK": ["formula one", "f1", "liberty media"],
    "LYV": ["live nation", "ticketmaster"],
    "MSG": ["madison square garden"],
    "MSGS": ["msg sports"],
    "MSGE": ["msg entertainment"],
    "EDR": ["endeavor"],
    "WMG": ["warner music"],
    "SPOT": ["spotify"],
    "SIRI": ["siriusxm", "sirius"],
    "NYT": ["new york times", "nyt"],
    "NWSA": ["news corp", "wall street journal", "dow jones"],
    "GCI": ["gannett", "usa today"],
    "TGNA": ["tegna"],
    "GTN": ["gray television"],
    "SSP": ["scripps"],
    "SBGI": ["sinclair"],
    
    # Telecom
    "T": ["at&t", "att"],
    "VZ": ["verizon"],
    "TMUS": ["t-mobile", "tmobile"],
    "VOD": ["vodafone"],
    "ORAN": ["orange"],
    "TEF": ["telefonica"],
    "AMX": ["america movil"],
    "CHL": ["china mobile"],
    "CHU": ["china unicom"],
    "LUMN": ["lumen"],
    "FYBR": ["frontier"],
    "USM": ["u.s. cellular"],
    "SHEN": ["shenandoah"],
    "GSAT": ["globalstar"],
    "IRDM": ["iridium"],
    
    # Real estate
    "AMT": ["american tower"],
    "CCI": ["crown castle"],
    "SBAC": ["sba communications"],
    "EQIX": ["equinix"],
    "DLR": ["digital realty"],
    "PLD": ["prologis"],
    "SPG": ["simon property", "simon"],
    "O": ["realty income"],
    "VICI": ["vici properties"],
    "WPC": ["w.p. carey"],
    "NNN": ["national retail properties"],
    "AVB": ["avalonbay"],
    "EQR": ["equity residential"],
    "ESS": ["essex property"],
    "MAA": ["mid america apartment"],
    "UDR": ["udr"],
    "CPT": ["camden property"],
    "INVH": ["invitation homes"],
    "AMH": ["american homes"],
    "SUI": ["sun communities"],
    "ELS": ["equity lifestyle"],
    "PSA": ["public storage"],
    "EXR": ["extra space storage"],
    "CUBE": ["cubesmart"],
    "LSI": ["life storage"],
    "NSA": ["national storage affiliates"],
    "COLD": ["americold"],
    
    # Industrials
    "CAT": ["caterpillar"],
    "DE": ["john deere", "deere"],
    "AGCO": ["agco"],
    "CNHI": ["cnh industrial", "case ih", "new holland"],
    "HON": ["honeywell"],
    "MMM": ["3m"],
    "GE": ["general electric", "ge"],
    "ETN": ["eaton"],
    "EMR": ["emerson"],
    "ROK": ["rockwell automation"],
    "AME": ["ametek"],
    "ITW": ["illinois tool works"],
    "PH": ["parker hannifin"],
    "DOV": ["dover"],
    "XYL": ["xylem"],
    "IEX": ["idex"],
    "GNRC": ["generac"],
    "SWK": ["stanley black decker"],
    "TTC": ["toro company"],
    "REVG": ["rev group"],
    "OSK": ["oshkosh"],
    "PCAR": ["paccar"],
    "CMI": ["cummins"],
    "ALSN": ["allison transmission"],
    "GNTX": ["gentex"],
    "LEA": ["lear"],
    "MGA": ["magna"],
    "BWA": ["borgwarner"],
    "DAN": ["dana"],
    "VC": ["visteon"],
    "APTV": ["aptiv"],
    "ALV": ["autoliv"],
    
    # Utilities
    "NEE": ["nextera", "fpl"],
    "DUK": ["duke energy"],
    "SO": ["southern company"],
    "D": ["dominion"],
    "AEP": ["aep", "american electric power"],
    "EXC": ["exelon"],
    "XEL": ["xcel"],
    "ED": ["consolidated edison", "con ed"],
    "PEG": ["pseg", "public service enterprise"],
    "WEC": ["wec energy"],
    "ES": ["eversource"],
    "EIX": ["edison international", "sce"],
    "DTE": ["dte energy"],
    "PPL": ["ppl"],
    "FE": ["firstenergy"],
    "AEE": ["ameren"],
    "CMS": ["cms energy"],
    "CNP": ["centerpoint"],
    "ETR": ["entergy"],
    "EVRG": ["evergy"],
    "AWK": ["american water works"],
    "WTR": ["essential utilities"],
    "SJW": ["sjw group"],
    "CWT": ["california water"],
    
    # Insurance
    "BRK-B": ["berkshire hathaway", "berkshire", "warren buffett"],
    "CB": ["chubb"],
    "TRV": ["travelers"],
    "PGR": ["progressive"],
    "ALL": ["allstate"],
    "MET": ["metlife"],
    "PRU": ["prudential"],
    "AIG": ["aig"],
    "AFL": ["aflac"],
    "LNC": ["lincoln national"],
    "CINF": ["cincinnati financial"],
    "WRB": ["w.r. berkley"],
    "HIG": ["hartford"],
    "CNA": ["cna financial"],
    "RE": ["everest re"],
    "RNR": ["renaissancere"],
    "AJG": ["arthur j gallagher"],
    "MMC": ["marsh mclennan", "marsh"],
    "AON": ["aon"],
    "BRO": ["brown brown", "brown & brown"],
    "WTW": ["willis towers watson"],
    
    # Asset management
    "BLK": ["blackrock", "larry fink"],
    "BX": ["blackstone"],
    "KKR": ["kkr"],
    "APO": ["apollo"],
    "CG": ["carlyle"],
    "ARES": ["ares management"],
    "OWL": ["blue owl"],
    "TROW": ["t rowe price", "t. rowe price"],
    "IVZ": ["invesco"],
    "FHI": ["federated hermes"],
    "BEN": ["franklin templeton"],
    "VCTR": ["victory capital"],
    "AMG": ["affiliated managers"],
    "AB": ["alliancebernstein"],
    "JHG": ["janus henderson"],
    "SEIC": ["sei investments"],
    "EV": ["eaton vance"],
    "FII": ["federated investors"],
    
    # ETFs and indices (for market news)
    "SPY": ["s&p 500", "s&p500", "sp500", "spy"],
    "QQQ": ["nasdaq", "nasdaq 100", "qqq"],
    "DIA": ["dow jones", "dow", "djia"],
    "IWM": ["russell 2000", "russell", "iwm"],
    "VTI": ["total market", "vti"],
    "VIX": ["vix", "volatility index", "fear index"],
}


@lru_cache(maxsize=1)
def get_comprehensive_company_mapping() -> dict[str, str]:
    """
    Generate a comprehensive mapping of company names/aliases to ticker symbols.
    
    Returns a dict where keys are lowercase company names/aliases and values are ticker symbols.
    """
    mapping: dict[str, str] = {}
    
    # 1. Add S&P 500 companies
    for company in load_sp500():
        ticker = company.ticker
        security = company.security
        
        # Full name
        normalized = _normalize(security)
        if normalized and len(normalized) >= 3:
            mapping[normalized] = ticker
        
        # Stripped (without corp suffixes)
        stripped = _strip_corp_suffixes(normalized)
        if stripped and len(stripped) >= 3:
            mapping[stripped] = ticker
        
        # Remove .com suffix
        no_com = stripped.replace(" com", "").strip()
        if no_com and len(no_com) >= 3:
            mapping[no_com] = ticker
        
        # Remove parenthetical content (e.g., "Class A")
        no_paren = _normalize(re.sub(r"\s*\(.*?\)\s*", "", security))
        if no_paren and len(no_paren) >= 3:
            mapping[no_paren] = ticker
        
        stripped_no_paren = _strip_corp_suffixes(no_paren)
        if stripped_no_paren and len(stripped_no_paren) >= 3:
            mapping[stripped_no_paren] = ticker
    
    # 2. Add short name aliases from S&P 500 service
    for ticker, aliases in _SHORT_NAME_ALIASES.items():
        for alias in aliases:
            normalized = _normalize(alias)
            if normalized and len(normalized) >= 2:
                mapping[normalized] = ticker
    
    # 3. Add common short names (google, apple, amazon, etc.)
    for ticker, short_names in _COMMON_SHORT_NAMES.items():
        for name in short_names:
            normalized = _normalize(name)
            if normalized and len(normalized) >= 2:
                mapping[normalized] = ticker
    
    # 4. Add extra companies (non-S&P 500)
    for ticker, aliases in _EXTRA_COMPANIES.items():
        for alias in aliases:
            normalized = _normalize(alias)
            if normalized and len(normalized) >= 2:
                mapping[normalized] = ticker
    
    return mapping


@lru_cache(maxsize=1)
def get_ticker_to_names() -> dict[str, list[str]]:
    """
    Generate reverse mapping: ticker -> list of company names/aliases.
    """
    result: dict[str, list[str]] = {}
    
    for name, ticker in get_comprehensive_company_mapping().items():
        if ticker not in result:
            result[ticker] = []
        if name not in result[ticker]:
            result[ticker].append(name)
    
    return result


def resolve_company_to_ticker(name: str) -> str | None:
    """
    Resolve a company name or alias to its ticker symbol.
    """
    normalized = _normalize(name)
    if not normalized:
        return None
    
    mapping = get_comprehensive_company_mapping()
    
    # Direct match
    if normalized in mapping:
        return mapping[normalized]
    
    # Try stripped version
    stripped = _strip_corp_suffixes(normalized)
    if stripped and stripped in mapping:
        return mapping[stripped]
    
    return None


def generate_js_company_mapping() -> str:
    """
    Generate JavaScript code for the COMPANY_TO_TICKER mapping.
    This can be used to update the content script.
    """
    mapping = get_comprehensive_company_mapping()
    
    # Sort by name length (longest first) for proper matching
    sorted_items = sorted(mapping.items(), key=lambda x: (-len(x[0]), x[0]))
    
    lines = ["const COMPANY_TO_TICKER = {"]
    for name, ticker in sorted_items:
        # Skip very short names (< 3 chars) as they cause false positives
        if len(name) < 3:
            continue
        # Skip names that are just the ticker itself
        if name.upper() == ticker:
            continue
        # Escape single quotes in name
        safe_name = name.replace("'", "\\'")
        lines.append(f"  '{safe_name}': '{ticker}',")
    lines.append("};")
    
    return "\n".join(lines)
