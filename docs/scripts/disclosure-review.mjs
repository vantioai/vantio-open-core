const TIP = "60726bef7a7d7da35525a4d832ec63b5f8ca5bad";
const PRIVATE_TIP = "d876ced0531607b7468efa3d0da981821be2cbbc";
const WORDING_COMMIT = "ec633d192544c22cde2853226b3f8e77d753a49f";

const PUBLIC_COMMITS = [
  "8baead08d12192799ad51bae6f411cd394c444e4",
  "dada18b428ec4caadc0f799a7a4c38e2e599032b",
  "9bd056f66ed4ea2fe6aff93f62aacbd3b0e06821",
  "aca55ef3fc2b01b6e1643ecb752185f492e4be77",
  "2f0cb57ebd2a7558d99f5cf73f352d0b497c6f3e",
  "bb70c56f5755d0d9cdbd3c165e01f7076704faec",
  "949063873365e804a6d2ebddc39d97ea584b3f22",
  TIP,
];

const REVIEWED_FILES = [
  ["ARCHITECTURE-BOUNDARIES.md", "d79fe88e373442b0164ac02866c068db15c1c5a1", "075642b3b8797d505b59130b7c0374d0ffaad89fa7bafebc2ebee8ac83fa66e5", 7162, "MATCHES_PUBLIC_TIP", "d79fe88e373442b0164ac02866c068db15c1c5a1", 7162],
  ["BACKUP-AND-RECOVERY.md", "6432fa61cb5112b605df9b2e85a37292f5187bc6", "34e4f6b1f8917f2969374f090c99b5ab19977ccbd0ad0818de2c9e503c49e55b", 4932, "MATCHES_PUBLIC_TIP", "6432fa61cb5112b605df9b2e85a37292f5187bc6", 4932],
  ["CUSTOMER-AI-GUIDE.md", "84d17c495ebb86642462d1be64773e7d05339688", "c389ed3eab8d5dbb73de52fa9f8a9393aff79820eb9abb6cd5f93698bc632ed6", 4843, "MATCHES_PUBLIC_TIP", "84d17c495ebb86642462d1be64773e7d05339688", 4843],
  ["CUSTOMER-OVERVIEW.md", "e039a083b800cb35f92de80a67658f931224c74d", "8499a295d393496bc901d441df7f56d8482c4c60c82b13f2db650201b857974e", 8250, "WORDING_FIX", "3d4de013f6da9db6418a02cedf6c5009d1b95356", 8262],
  ["CUSTOMER-RELEASE-NOTES.md", "b3d4f48a8ca41fa84db89f46fd09cbdaf21e4d2d", "fb3c606e44063cf70fa8bf27dbbacda9ce31fb6c137a4cd436df1d6b090ff5df", 3144, "MATCHES_PUBLIC_TIP", "b3d4f48a8ca41fa84db89f46fd09cbdaf21e4d2d", 3144],
  ["DEPLOYMENT-GUIDE.md", "9564fcd84ef96303dc655355719e7c186feeac48", "22df6e9762724c2904675722e58c8b2c2e88256c39469092508340e9769647f3", 7925, "MATCHES_PUBLIC_TIP", "9564fcd84ef96303dc655355719e7c186feeac48", 7925],
  ["ENROLLMENT-GUIDE.md", "a226b761c21d53c542db09320a1ef24af0bae4c9", "e6784ab19d25e78666059c68b1cb6a8b63d6c1e8ab599d80e575a8aaea313e34", 5411, "MATCHES_PUBLIC_TIP", "a226b761c21d53c542db09320a1ef24af0bae4c9", 5411],
  ["EVIDENCE-AND-ASSURANCE.md", "680fba001bfec6b8915511ff58d679b5084e0858", "144b3bb92e1eaa4bd3dcc0a5b815ed1012e044fb2ffeca202b3edbf9ff53ed62", 6506, "WORDING_FIX", "3c68008c6702f8daf082c1315aaa2f0072ca9109", 6502],
  ["INCIDENT-RESPONSE.md", "c7a662dadc9d7b3215882b5b8470ba6404c78c9f", "f2f776fb340b4ace024460583a84bb12ec45343a49ad2bf7482537fc6d6a1b89", 4990, "MATCHES_PUBLIC_TIP", "c7a662dadc9d7b3215882b5b8470ba6404c78c9f", 4990],
  ["KNOWN-LIMITATIONS.md", "e653036404bc7c27ba926c9eb6463514f3e9dcb5", "316e6df5078716f9c48dcb55fcb6ced076704bef92cd148b4b758edb2d77a1af", 5776, "MATCHES_PUBLIC_TIP", "e653036404bc7c27ba926c9eb6463514f3e9dcb5", 5776],
  ["OPERATIONS-RUNBOOK.md", "af03a89e6122190b813336d54b98faa90f9c42fb", "b278730c0a689ec73e965e9a43c085977ff3da093420f43e4de6f3f0d0a21699", 6014, "MATCHES_PUBLIC_TIP", "af03a89e6122190b813336d54b98faa90f9c42fb", 6014],
  ["POLICY-GUIDE.md", "bea4581739ba1bd7843534a055f302627a06ed9a", "11cb4ea7ed42a56b71329cbee1404eb9ba2abce530195a2cb2faf029441acee6", 6893, "MATCHES_PUBLIC_TIP", "bea4581739ba1bd7843534a055f302627a06ed9a", 6893],
  ["REMOVAL-AND-UNINSTALL.md", "fb7c5c6c5d031b6bd7fdb9ca7884f342e54750d8", "22a4fb0a9d5884ab344ca114e7c48e810b209b204e8f6200c6bbbf116a86de57", 4124, "MATCHES_PUBLIC_TIP", "fb7c5c6c5d031b6bd7fdb9ca7884f342e54750d8", 4124],
  ["SECURITY-GUIDE.md", "15cea6bc857a953bd20a6b2aab008a5266f36f55", "4ad6ce02f19f78c198bea75ed645f2a6e72ca010d679ab82cb4974e085a40a14", 5456, "MATCHES_PUBLIC_TIP", "15cea6bc857a953bd20a6b2aab008a5266f36f55", 5456],
  ["SUPPORTED-ENVIRONMENTS.md", "8fbeef34ee69916759e0f5314154980f563b166b", "0591becc1be26633ab925bcfa21f6a3a96ff09a9b7d589de50b14138640c38fe", 6181, "MATCHES_PUBLIC_TIP", "8fbeef34ee69916759e0f5314154980f563b166b", 6181],
  ["TROUBLESHOOTING.md", "493e5fa1a570c37cc23a587f47c5282e1213c5d9", "34b0e4b0caa582bd7024fed73663e9636b6e79452b3a2b2c54ce938122e0fe04", 7051, "MATCHES_PUBLIC_TIP", "493e5fa1a570c37cc23a587f47c5282e1213c5d9", 7051],
  ["UPGRADE-AND-ROLLBACK.md", "3cd040b9e4dc8795a0e4cfe0a6e4965aeb3c4d01", "aa44cd444c738bde27769c0e1f88b092d77efae9e45390229531a329dda94dfa", 4697, "MATCHES_PUBLIC_TIP", "3cd040b9e4dc8795a0e4cfe0a6e4965aeb3c4d01", 4697],
  ["VERSION-METADATA.json", "75cb1522951573346b84869cb76c94213e9f34bd", "bb7b873f546b894dfe00bd9f0594a558199817b72925608bff325f99e95ed400", 2130, "MATCHES_PUBLIC_TIP", "75cb1522951573346b84869cb76c94213e9f34bd", 2130],
];

function row(entry) {
  return {
    path: entry[0],
    public_tip_git_blob: entry[1],
    public_tip_sha256: entry[2],
    public_tip_bytes: entry[3],
    private_bytes: entry[4],
    private_git_blob: entry[5],
    private_bytes_size: entry[6],
  };
}

export const REVIEWED_MANUAL_FILES = REVIEWED_FILES.map(row);

function hex(value, length) {
  return typeof value === "string" && new RegExp(`^[0-9a-f]{${length}}$`).test(value);
}

export function disclosureRecordProblems(record) {
  const problems = [];
  if (!record || record.schema !== "vantio.disclosure.pe-public-draft/v1") {
    problems.push("disclosure schema drifted");
  }
  if (record?.audience !== "INTERNAL_RESTRICTED") problems.push("audience drifted");
  if (record?.classification !== "DISCLOSURE_GOVERNANCE_CLEANUP_READY_FOR_COUNCIL") {
    problems.push("classification drifted");
  }
  if (record?.council_status !== "PENDING_INDEPENDENT_COUNCIL") problems.push("council status is not pending");
  const pr = record?.public_pull_request;
  if (pr?.number !== 66) problems.push("pull request number drifted");
  if (pr?.state !== "closed") problems.push("pull request is not closed");
  if (pr?.merged !== false || pr?.merged_at !== null) problems.push("pull request is not unmerged");
  if (pr?.head_sha !== TIP) problems.push("public tip drifted");
  if (pr?.branch_ref_on_origin !== "ABSENT") problems.push("branch ref is not recorded absent");
  if (pr?.pull_ref !== "refs/pull/66/head" || pr?.pull_ref_sha !== TIP) {
    problems.push("pull ref drifted");
  }
  if (record?.merge_to_public_main !== "NOT_AUTHORIZED") problems.push("public main merge is not closed");
  if (record?.history_rewrite?.git_filter_repo_run !== false) problems.push("history rewrite is recorded as run");
  if (record?.history_rewrite?.force_push !== false) problems.push("force push is recorded as run");
  const purge = record?.support_purge;
  if (purge?.status !== "PREPARED_NOT_SENT") problems.push("purge packet status is not prepared");
  if (purge?.contacted_github_support !== false) problems.push("GitHub Support is recorded as contacted");
  const channel = record?.private_channel;
  if (channel?.repo !== "vantioai/vantio-pe-customer-docs") problems.push("private repo drifted");
  if (channel?.visibility !== "private") problems.push("private repo visibility drifted");
  if (channel?.forking !== false) problems.push("private repo forking drifted");
  if (channel?.main_tip !== PRIVATE_TIP) problems.push("private tip drifted");
  if (channel?.wording_fix_commit !== WORDING_COMMIT) problems.push("wording commit drifted");
  if (channel?.manual_bytes_copied_into_open_core !== false) problems.push("manual bytes are marked copied");
  if (channel?.anonymous_http_status !== 404) problems.push("anonymous status drifted");
  const commits = record?.public_commits;
  if (!Array.isArray(commits) || commits.length !== PUBLIC_COMMITS.length) {
    problems.push("public commit list length drifted");
  } else if (commits.some((sha, index) => sha !== PUBLIC_COMMITS[index])) {
    problems.push("public commit list drifted");
  }
  if (record?.reachable_from_main !== false) problems.push("tip is marked reachable from main");
  const files = record?.reviewed_hashes?.files;
  if (!Array.isArray(files) || files.length !== REVIEWED_MANUAL_FILES.length) {
    problems.push("reviewed file count drifted");
  } else {
    files.forEach((file, index) => {
      const expected = REVIEWED_MANUAL_FILES[index];
      for (const key of Object.keys(expected)) {
        if (file[key] !== expected[key]) problems.push(`${expected.path} ${key} drifted`);
      }
      if (!hex(file.public_tip_git_blob, 40) || !hex(file.public_tip_sha256, 64) || !hex(file.private_git_blob, 40)) {
        problems.push(`${file.path} hash shape drifted`);
      }
    });
  }
  const wording = (files || []).filter((file) => file.private_bytes === "WORDING_FIX");
  if (wording.length !== 2) problems.push("wording-fix count drifted");
  return problems;
}

export function purgePacketProblems(text) {
  const problems = [];
  const body = typeof text === "string" ? text : "";
  const required = [
    "PACKET_STATUS: PREPARED_NOT_SENT",
    "GITHUB_SUPPORT_CONTACTED: false",
    "PUBLIC_PR_66_STATE: CLOSED_UNMERGED",
    `TIP: ${TIP}`,
    "PULL_REF: refs/pull/66/head",
    "HISTORY_REWRITE_OF_MAIN: NOT_PERFORMED",
    "FILTER_REPO_RUN: false",
    "MERGE_TO_PUBLIC_MAIN: NOT_AUTHORIZED",
    "vantioai/vantio-open-core",
    "vantioai/vantio-pe-customer-docs",
    "This force did not submit this packet.",
  ];
  for (const token of required) {
    if (!body.includes(token)) problems.push(`purge packet missing ${token}`);
  }
  if (body.includes("PACKET_STATUS: SENT")) problems.push("purge packet is marked sent");
  if (body.includes("GITHUB_SUPPORT_CONTACTED: true")) problems.push("purge packet says support was contacted");
  if (body.includes("manual body:")) problems.push("purge packet includes a manual body marker");
  return problems;
}
