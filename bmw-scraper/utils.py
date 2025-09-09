def block_ads(route):
    url = route.request.url
    ad_keywords = [
    # Original keywords
    "ads", "doubleclick", "adservice", "googlesyndication",
    
    # Google Ad Services
    "googleadservices", "googletagservices", "googletagmanager", 
    "googlesyndication", "googleadservices", "adsystem", "adsense",
    "adnxs", "googleads", "admob", "adx", "adsystem.google",

    # Amazon
    "amazon-adsystem", "amazoncloudsearch", "amazontrustservices",
    "media-amazon", "assoc-amazon", "amazon-adsystem.com",

    # Facebook/Meta
    "facebook", "fbcdn", "connect.facebook", "staticxx.facebook",
    "fbsbx", "instagram", "whatsapp",

    # Microsoft
    "ads.microsoft", "bing", "msads", "microsoft", "msn",
    "live", "adsystem.microsoft", "clarity.ms",

    # Yahoo/Verizon Media
    "yahoo", "yimg", "advertising", "gemini.yahoo", "adnxs.com",
    "media.net", "adsystem.yahoo",

    # Twitter/X
    "ads-twitter", "analytics.twitter", "twitter", "twimg",
    "ads-api.twitter",

    # Ad Networks & Exchanges
    "admeld", "adsystem", "adnxs", "rubiconproject", "openx",
    "pubmatic", "appnexus", "criteo", "outbrain", "taboola",
    "revcontent", "smartadserver", "contextweb", "casalemedia",
    "adsystem", "turn", "rlcdn", "bluekai", "demdex", "everesttech",

    # Analytics & Tracking
    "googleanalytics", "google-analytics", "analytics", "gtag",
    "hotjar", "crazyegg", "optimizely", "mixpanel", "segment",
    "amplitude", "fullstory", "loggly", "newrelic", "bugsnag",
    "sentry", "rollbar", "trackjs", "errorception",

    # CDNs often used for ads
    "googlesyndication", "googletagservices", "doubleclick",
    "amazon-adsystem", "media-amazon", "cloudfront",

    # Social Media Widgets
    "addthis", "sharethis", "facebook", "twitter", "linkedin",
    "pinterest", "tumblr", "reddit", "vk", "ok.ru",

    # Behavioral Targeting
    "adsystem", "advertising", "doubleclick", "googleadservices",
    "facebook", "bing", "yahoo", "amazon-adsystem", "criteo",
    "outbrain", "taboola", "revcontent", "smartadserver",

    # Video Ads
    "imasdk.googleapis", "youtube", "vimeo", "jwplayer",
    "brightcove", "kaltura", "ooyala", "theplatform",

    # Mobile Ad Networks
    "admob", "inmobi", "millennial", "jumptap", "mdotm",
    "mobclix", "nexage", "smaato", "mojiva", "tapjoy",
    "chartboost", "unity3d", "ironsource", "vungle",

    # Affiliate Networks
    "commission-junction", "linksynergy", "shareasale",
    "clickbank", "affiliate", "rakuten", "impact",

    # Retargeting
    "criteo", "adroll", "perfectaudience", "retargeter",
    "chango", "triggit", "fetchback", "struq",

    # Common ad-related subdomains and paths
    "ad", "ads", "adserver", "adserv", "advertising", "advert",
    "banner", "banners", "click", "tracker", "tracking", "track",
    "pixel", "beacon", "analytics", "stats", "metrics", "counter",
    "affiliate", "promo", "promotion", "marketing", "campaign",

    # International ad networks
    "yandex", "baidu", "naver", "sina", "sohu", "qq", "163",
    "rambler", "mail.ru", "vk", "odnoklassniki", "badoo",
    
    "rtb" , "primis", "primis.tech", "adform", "adform.net",
    ]
    if any(keyword in url for keyword in ad_keywords):
        #print(f"Blocking ad request: {url}")
        route.abort()
    else:
        route.continue_()