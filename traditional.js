const tdS2TPhrases = {
  "\u5e03\u4f26\u7279": "\u5e03\u862d\u7279",
  "\u539f\u6cb9\u671f\u8d27": "\u539f\u6cb9\u671f\u8ca8",
  "\u5fc3\u7406\u5173\u53e3": "\u5fc3\u7406\u95dc\u53e3",
  "\u6574\u6570\u4f4d": "\u6574\u6578\u4f4d",
  "\u65e5\u5185": "\u65e5\u5167",
  "\u5f53\u524d": "\u7576\u524d",
  "\u4ee5\u6765": "\u4ee5\u4f86",
  "\u5feb\u8baf": "\u5feb\u8a0a",
  "\u8d44\u672c": "\u8cc7\u672c",
  "\u80cc\u540e": "\u80cc\u5f8c",
  "\u8d27\u5e01": "\u8ca8\u5e63",
  "\u96be\u9898": "\u96e3\u984c",
  "\u8054\u624b": "\u806f\u624b",
  "\u963f\u6ce2\u7f57": "\u963f\u6ce2\u7f85",
  "\u8bbe\u7acb": "\u8a2d\u7acb",
  "\u878d\u8d44": "\u878d\u8cc7",
  "\u9996\u7b14": "\u9996\u7b46",
  "\u4ebf\u7f8e\u5143": "\u5104\u7f8e\u5143",
  "\u9996\u4e2a": "\u9996\u500b",
  "\u5ba2\u6237": "\u5ba2\u6236"
};

const tdS2TChars = {
  "\u4e0e":"\u8207","\u4e1a":"\u696d","\u4e1c":"\u6771","\u4e2a":"\u500b","\u4e3a":"\u70ba","\u4e66":"\u66f8","\u4e70":"\u8cb7","\u4e91":"\u96f2","\u4ea7":"\u7522","\u4ebf":"\u5104","\u4ec5":"\u50c5","\u4ece":"\u5f9e","\u4ed3":"\u5009","\u4eea":"\u5100","\u4ef7":"\u50f9","\u4f17":"\u773e","\u4f18":"\u512a","\u4f1a":"\u6703","\u4f20":"\u50b3","\u4f24":"\u50b7","\u4f26":"\u502b","\u4f53":"\u9ad4","\u4f59":"\u9918","\u503a":"\u50b5","\u50a8":"\u5132","\u5170":"\u862d","\u5173":"\u95dc","\u5174":"\u8208","\u517b":"\u990a","\u5185":"\u5167","\u519c":"\u8fb2","\u51b2":"\u885d","\u51b3":"\u6c7a","\u51b5":"\u6cc1","\u51c6":"\u6e96","\u51fb":"\u64ca","\u5219":"\u5247","\u521b":"\u5275","\u522b":"\u5225","\u5242":"\u5291","\u529e":"\u8fa6","\u52a1":"\u52d9","\u52a8":"\u52d5","\u52bf":"\u52e2","\u533a":"\u5340","\u534f":"\u5354","\u5355":"\u55ae","\u5356":"\u8ce3","\u538b":"\u58d3","\u53bf":"\u7e23","\u53c2":"\u53c3","\u53cc":"\u96d9","\u53d1":"\u767c","\u53d8":"\u8b8a","\u53f6":"\u8449","\u53f7":"\u865f","\u540e":"\u5f8c","\u542f":"\u555f","\u5458":"\u54e1","\u5468":"\u9031","\u54cd":"\u97ff","\u56e2":"\u5718","\u56ed":"\u5712","\u56fd":"\u570b","\u56fe":"\u5716","\u573a":"\u5834","\u5757":"\u584a","\u575a":"\u5805","\u58f0":"\u8072","\u5904":"\u8655","\u5907":"\u5099","\u590d":"\u5fa9","\u5934":"\u982d","\u5956":"\u734e","\u5b66":"\u5b78","\u5b9d":"\u5bf6","\u5b9e":"\u5be6","\u5ba1":"\u5be9","\u5bbd":"\u5bec","\u5bfc":"\u5c0e","\u5c06":"\u5c07","\u5c14":"\u723e","\u5c42":"\u5c64","\u5c5e":"\u5c6c","\u5e01":"\u5e63","\u5e08":"\u5e2b","\u5e26":"\u5e36","\u5e2e":"\u5e6b","\u5e7f":"\u5ee3","\u5e86":"\u6176","\u5e93":"\u5eab","\u5e94":"\u61c9","\u5f00":"\u958b","\u5f02":"\u7570","\u5f20":"\u5f35","\u5f3a":"\u5f37","\u5f52":"\u6b78","\u5f55":"\u9304","\u6218":"\u6230","\u6267":"\u57f7","\u6269":"\u64f4","\u626b":"\u6383","\u6270":"\u64fe","\u62a4":"\u8b77","\u62a5":"\u5831","\u62c5":"\u64d4","\u62df":"\u64ec","\u62e5":"\u64c1","\u62e9":"\u64c7","\u6325":"\u63ee","\u635f":"\u640d","\u636e":"\u64da","\u6446":"\u64fa","\u6570":"\u6578","\u65f6":"\u6642","\u65e0":"\u7121","\u663e":"\u986f","\u6682":"\u66ab","\u672f":"\u8853","\u673a":"\u6a5f","\u6743":"\u6b0a","\u6765":"\u4f86","\u6781":"\u6975","\u6784":"\u69cb","\u6807":"\u6a19","\u6837":"\u6a23","\u68c0":"\u6aa2","\u6b27":"\u6b50","\u6c14":"\u6c23","\u6c47":"\u532f","\u6c49":"\u6f22","\u6ca1":"\u6c92","\u6d4b":"\u6e2c","\u6d4e":"\u6fdf","\u6e29":"\u6eab","\u6e7e":"\u7063","\u6ee1":"\u6eff","\u7075":"\u9748","\u70b9":"\u9ede","\u70bc":"\u7149","\u70ed":"\u71b1","\u7231":"\u611b","\u72b6":"\u72c0","\u72ec":"\u7368","\u73af":"\u74b0","\u73b0":"\u73fe","\u7535":"\u96fb","\u753b":"\u756b","\u76d1":"\u76e3","\u76d8":"\u76e4","\u77ff":"\u7926","\u7801":"\u78bc","\u786e":"\u78ba","\u79bb":"\u96e2","\u79cd":"\u7a2e","\u79ef":"\u7a4d","\u79f0":"\u7a31","\u7ade":"\u7af6","\u7b14":"\u7b46","\u7b7e":"\u7c3d","\u7b80":"\u7c21","\u7c7b":"\u985e","\u7ea7":"\u7d1a","\u7ebf":"\u7dda","\u7ec4":"\u7d44","\u7ec6":"\u7d30","\u7ec8":"\u7d42","\u7ecf":"\u7d93","\u7ed3":"\u7d50","\u7ed9":"\u7d66","\u7edf":"\u7d71","\u7ee7":"\u7e7c","\u7eed":"\u7e8c","\u7ef4":"\u7dad","\u7f51":"\u7db2","\u8054":"\u806f","\u8111":"\u8166","\u817e":"\u9a30","\u8282":"\u7bc0","\u82cf":"\u8607","\u82f9":"\u860b","\u8303":"\u7bc4","\u8363":"\u69ae","\u83b7":"\u7372","\u8425":"\u71df","\u84dd":"\u85cd","\u8865":"\u88dc","\u88c5":"\u88dd","\u89c1":"\u898b","\u89c2":"\u89c0","\u89c4":"\u898f","\u89c6":"\u8996","\u8ba1":"\u8a08","\u8ba4":"\u8a8d","\u8ba8":"\u8a0e","\u8bad":"\u8a13","\u8bb0":"\u8a18","\u8bb2":"\u8b1b","\u8bbe":"\u8a2d","\u8bbf":"\u8a2a","\u8bc1":"\u8b49","\u8bc4":"\u8a55","\u8bc6":"\u8b58","\u8bc9":"\u8a34","\u8bd5":"\u8a66","\u8bdd":"\u8a71","\u8be2":"\u8a62","\u8be5":"\u8a72","\u8be6":"\u8a73","\u8bed":"\u8a9e","\u8bf7":"\u8acb","\u8c03":"\u8abf","\u8c08":"\u8ac7","\u8c22":"\u8b1d","\u8d1f":"\u8ca0","\u8d22":"\u8ca1","\u8d27":"\u8ca8","\u8d28":"\u8cea","\u8d2d":"\u8cfc","\u8d39":"\u8cbb","\u8d44":"\u8cc7","\u8d5a":"\u8cfa","\u8d5b":"\u8cfd","\u8f66":"\u8eca","\u8f6c":"\u8f49","\u8f6f":"\u8edf","\u8f7b":"\u8f15","\u8f7d":"\u8f09","\u8f83":"\u8f03","\u8f91":"\u8f2f","\u8f93":"\u8f38","\u8fbe":"\u9054","\u8fc7":"\u904e","\u8fd0":"\u904b","\u8fd8":"\u9084","\u8fdb":"\u9032","\u8fdc":"\u9060","\u8fde":"\u9023","\u9009":"\u9078","\u90ae":"\u90f5","\u91c7":"\u63a1","\u91ca":"\u91cb","\u91cc":"\u88e1","\u94fe":"\u93c8","\u9519":"\u932f","\u952e":"\u9375","\u95e8":"\u9580","\u95ee":"\u554f","\u95f4":"\u9593","\u961f":"\u968a","\u9633":"\u967d","\u9645":"\u969b","\u9669":"\u96aa","\u96be":"\u96e3","\u9875":"\u9801","\u9884":"\u9810","\u9886":"\u9818","\u9898":"\u984c","\u98ce":"\u98a8","\u98de":"\u98db","\u9a8c":"\u9a57","\u9ec4":"\u9ec3"};

function tdToTraditional(value = "") {
  let text = String(value);
  Object.entries(tdS2TPhrases).forEach(([s, t]) => { text = text.replaceAll(s, t); });
  return text.replace(/[\u4e00-\u9fff]/g, (char) => tdS2TChars[char] || char);
}

function tdNormalizeNode(root = document.body) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    const converted = tdToTraditional(node.nodeValue);
    if (converted !== node.nodeValue) node.nodeValue = converted;
  });
  root.querySelectorAll?.("input[placeholder], textarea[placeholder], [title], [aria-label]").forEach((node) => {
    ["placeholder", "title", "aria-label"].forEach((attr) => {
      const value = node.getAttribute(attr);
      if (value) node.setAttribute(attr, tdToTraditional(value));
    });
  });
}

const tdObserver = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => {
    mutation.addedNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const converted = tdToTraditional(node.nodeValue);
        if (converted !== node.nodeValue) node.nodeValue = converted;
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        tdNormalizeNode(node);
      }
    });
  });
});

tdNormalizeNode();
tdObserver.observe(document.body, { childList: true, subtree: true });
