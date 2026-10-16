/* SPDX-License-Identifier: GPL-2.0-only
 *
 * T5 lab egress program. GPL-2.0-only because bpf_spin_lock is a GPL-only
 * helper. This file is not linked into the Python package.
 *
 * Attach points: cgroup_skb/egress, cgroup/connect4, cgroup/connect6.
 * One program per attach. No tail calls.
 *
 * The userspace entropy function is not called here. There is no floating-point logarithm and no histogram.
 * A left-hand label long enough to score is marked entropy_deferred and
 * left for userspace. That flag is not a drop.
 *
 * Label: the object may compile on a runner. Loading it is Roadmap until
 * a Vantio-owned host accepts it. The loader refuses every other host.
 *
 * reason:policy_permits
 * reason:policy_malformed
 * reason:resolver_not_allowed
 * reason:dns_name_not_allowed
 * reason:dns_label_too_long
 * reason:dns_label_not_ldh
 * reason:dns_unparsable
 * reason:dns_parse_budget
 * reason:dns_qdcount
 * reason:dns_query_volume
 * reason:dns_transport_not_visible
 * reason:link_local_not_allowed
 * reason:icmp_destination_not_allowed
 * reason:icmp_type_not_allowed
 * reason:icmp_header_unreadable
 * reason:loopback_port_not_allowed
 * reason:loopback_header_unreadable
 * reason:get_method_not_visible
 * reason:case_not_applicable
 * reason:address_not_canonical
 */

typedef unsigned char __u8;
typedef unsigned short __u16;
typedef unsigned int __u32;
typedef unsigned long long __u64;

#define SEC(NAME) __attribute__((section(NAME), used))
#define __uint(name, val) int (*name)[val]
#define __type(name, val) typeof(val) *name
#define __always_inline inline __attribute__((always_inline))

enum {
	T5_MAP_ARRAY = 2,
	T5_MAP_RINGBUF = 27,
};

enum {
	T5_PASS = 0,
	T5_CLASSIFIED = 1,
	T5_EVAL = 2,
	T5_SCOPE = 3,
};

enum t5_reason {
	T5_POLICY_PERMITS = 0,
	T5_POLICY_MALFORMED = 1,
	T5_RESOLVER_NOT_ALLOWED = 2,
	T5_DNS_NAME_NOT_ALLOWED = 3,
	T5_DNS_LABEL_TOO_LONG = 4,
	T5_DNS_LABEL_NOT_LDH = 5,
	T5_DNS_UNPARSABLE = 6,
	T5_DNS_PARSE_BUDGET = 7,
	T5_DNS_QDCOUNT = 8,
	T5_DNS_QUERY_VOLUME = 9,
	T5_DNS_TRANSPORT_NOT_VISIBLE = 10,
	T5_LINK_LOCAL_NOT_ALLOWED = 11,
	T5_ICMP_DESTINATION_NOT_ALLOWED = 12,
	T5_ICMP_TYPE_NOT_ALLOWED = 13,
	T5_ICMP_HEADER_UNREADABLE = 14,
	T5_LOOPBACK_PORT_NOT_ALLOWED = 15,
	T5_LOOPBACK_HEADER_UNREADABLE = 16,
	T5_GET_METHOD_NOT_VISIBLE = 17,
	T5_CASE_NOT_APPLICABLE = 18,
	T5_ADDRESS_NOT_CANONICAL = 19,
};

/* Field order is the loader's struct format '<Q10I'. */
struct t5_cfg {
	__u64 window_ns;
	__u32 enforce;
	__u32 max_label;
	__u32 max_queries;
	__u32 entropy_min_length;
	__u32 entropy_userspace;
	__u32 n_names;
	__u32 n_resolvers;
	__u32 n_icmp;
	__u32 n_ports;
	__u32 pad;
};

struct bpf_spin_lock {
	__u32 val;
};

struct t5_window {
	struct bpf_spin_lock lock;
	__u32 pad;
	__u64 start_ns;
	__u32 count;
	__u32 pad2;
};

struct name_slot {
	__u32 len;
	__u8 bytes[64];
};

struct addr_slot {
	__u32 addr;
	__u32 set;
};

struct port_slot {
	__u32 port;
	__u32 set;
};

struct t5_event {
	__u32 reason;
	__u32 kind;
	__u32 entropy_deferred;
	__u16 dport;
	__u8 proto;
	__u8 pad;
};

/* Offsets match struct __sk_buff through data_end. */
struct t5_skb {
	__u32 len;
	__u32 pkt_type;
	__u32 mark;
	__u32 queue_mapping;
	__u32 protocol;
	__u32 vlan_present;
	__u32 vlan_tci;
	__u32 vlan_proto;
	__u32 priority;
	__u32 ingress_ifindex;
	__u32 ifindex;
	__u32 tc_index;
	__u32 cb[5];
	__u32 hash;
	__u32 tc_classid;
	__u32 data;
	__u32 data_end;
};

/* Offsets match struct bpf_sock_addr through protocol. */
struct t5_sock_addr {
	__u32 user_family;
	__u32 user_ip4;
	__u32 user_ip6[4];
	__u32 user_port;
	__u32 family;
	__u32 type;
	__u32 protocol;
};

struct {
	__uint(type, T5_MAP_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, struct t5_cfg);
} t5_cfg_map SEC(".maps");

struct {
	__uint(type, T5_MAP_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, struct t5_window);
} t5_window_map SEC(".maps");

struct {
	__uint(type, T5_MAP_ARRAY);
	__uint(max_entries, 4);
	__type(key, __u32);
	__type(value, struct name_slot);
} t5_name_map SEC(".maps");

struct {
	__uint(type, T5_MAP_ARRAY);
	__uint(max_entries, 4);
	__type(key, __u32);
	__type(value, struct addr_slot);
} t5_resolver_map SEC(".maps");

struct {
	__uint(type, T5_MAP_ARRAY);
	__uint(max_entries, 4);
	__type(key, __u32);
	__type(value, struct addr_slot);
} t5_icmp_map SEC(".maps");

struct {
	__uint(type, T5_MAP_ARRAY);
	__uint(max_entries, 8);
	__type(key, __u32);
	__type(value, struct port_slot);
} t5_port_map SEC(".maps");

struct {
	__uint(type, T5_MAP_RINGBUF);
	__uint(max_entries, 4096);
} t5_events SEC(".maps");

static void *(*bpf_map_lookup_elem)(void *map, const void *key) = (void *)1;
static long (*bpf_skb_load_bytes)(struct t5_skb *skb, __u32 offset, void *to, __u32 len) = (void *)26;
static __u64 (*bpf_ktime_get_ns)(void) = (void *)5;
static long (*bpf_spin_lock)(struct bpf_spin_lock *lock) = (void *)93;
static long (*bpf_spin_unlock)(struct bpf_spin_lock *lock) = (void *)94;
static void *(*bpf_ringbuf_reserve)(void *ringbuf, __u64 size, __u64 flags) = (void *)131;
static void (*bpf_ringbuf_submit)(void *data, __u64 flags) = (void *)132;

static __always_inline __u32 bswap32(__u32 value)
{
	return (value >> 24) | ((value >> 8) & 0xff00u) | ((value << 8) & 0xff0000u) | (value << 24);
}

static __always_inline __u16 bswap16(__u16 value)
{
	return (__u16)((value >> 8) | (value << 8));
}

static __always_inline int ldh(__u8 ch)
{
	if (ch >= 'a' && ch <= 'z')
		return 1;
	if (ch >= 'A' && ch <= 'Z')
		return 1;
	if (ch >= '0' && ch <= '9')
		return 1;
	if (ch == '-' || ch == '_')
		return 1;
	return 0;
}

static __always_inline int fold_byte(__u8 ch)
{
	if (ch >= 'A' && ch <= 'Z')
		return ch + 32;
	return ch;
}

static __always_inline int cfg_ok(struct t5_cfg *cfg)
{
	if (!cfg)
		return 0;
	if (cfg->entropy_userspace != 1)
		return 0;
	if (cfg->max_label < 1 || cfg->max_label > 63)
		return 0;
	if (cfg->max_queries < 1 || cfg->max_queries > 64)
		return 0;
	if (cfg->n_names > 4 || cfg->n_resolvers > 4 || cfg->n_icmp > 4 || cfg->n_ports > 8)
		return 0;
	if (cfg->window_ns == 0)
		return 0;
	return 1;
}

static __always_inline void emit(__u32 reason, __u32 kind, __u32 entropy, __u16 dport, __u8 proto)
{
	struct t5_event *event = bpf_ringbuf_reserve(&t5_events, sizeof(*event), 0);

	if (!event)
		return;
	event->reason = reason;
	event->kind = kind;
	event->entropy_deferred = entropy;
	event->dport = dport;
	event->proto = proto;
	event->pad = 0;
	bpf_ringbuf_submit(event, 0);
}

static __always_inline int finish(struct t5_cfg *cfg, __u32 reason, __u32 kind, __u32 entropy, __u16 dport, __u8 proto)
{
	emit(reason, kind, entropy, dport, proto);
	if (kind == T5_PASS)
		return 1;
	if (kind == T5_CLASSIFIED && cfg && cfg->enforce == 0)
		return 1;
	return 0;
}

static __always_inline int read8(struct t5_skb *skb, __u32 off, __u8 *out)
{
	if (off > 400)
		return -1;
	if (bpf_skb_load_bytes(skb, off, out, 1) < 0)
		return -1;
	return 0;
}

static __always_inline int addr_listed(void *map, __u32 count, __u32 addr)
{
	__u32 index;

	if (count > 4)
		count = 4;
	for (index = 0; index < 4; index++) {
		struct addr_slot *slot;

		if (index >= count)
			break;
		slot = bpf_map_lookup_elem(map, &index);
		if (slot && slot->set && slot->addr == addr)
			return 1;
	}
	return 0;
}

static __always_inline int port_listed(struct t5_cfg *cfg, __u32 port)
{
	__u32 index;
	__u32 count = cfg->n_ports;

	if (count > 8)
		count = 8;
	for (index = 0; index < 8; index++) {
		struct port_slot *slot;

		if (index >= count)
			break;
		slot = bpf_map_lookup_elem(&t5_port_map, &index);
		if (slot && slot->set && slot->port == port)
			return 1;
	}
	return 0;
}

static __always_inline int ipv4_loopback(__u32 addr)
{
	return (addr & 0xff000000u) == 0x7f000000u || (addr & 0xff000000u) == 0;
}

static __always_inline int ipv4_link_local(__u32 addr)
{
	return (addr & 0xffff0000u) == 0xa9fe0000u;
}

/* Returns 1 when the fixed window is over. *failed is an evaluation failure. */
static __always_inline int volume_over(struct t5_cfg *cfg, int *failed)
{
	__u32 key = 0;
	struct t5_window *window = bpf_map_lookup_elem(&t5_window_map, &key);
	__u64 now;
	int over = 0;

	*failed = 0;
	if (!window) {
		*failed = 1;
		return 1;
	}
	bpf_spin_lock(&window->lock);
	now = bpf_ktime_get_ns();
	if (window->start_ns != 0 && now < window->start_ns) {
		bpf_spin_unlock(&window->lock);
		*failed = 1;
		return 1;
	}
	if (window->start_ns == 0 || now - window->start_ns >= cfg->window_ns) {
		window->start_ns = now;
		window->count = 0;
	}
	if (window->count >= cfg->max_queries)
		over = 1;
	else
		window->count += 1;
	bpf_spin_unlock(&window->lock);
	return over;
}

static __always_inline int name_verdict(struct t5_cfg *cfg, __u8 *name, __u32 name_len, __u32 *entropy)
{
	__u32 index;
	__u32 best = 0;
	int matched = 0;
	__u32 count = cfg->n_names;

	*entropy = 0;
	if (count > 4)
		count = 4;
	for (index = 0; index < 4; index++) {
		struct name_slot *slot;
		__u32 len;
		__u32 pos;
		int same = 1;
		int suffix = 0;

		if (index >= count)
			break;
		slot = bpf_map_lookup_elem(&t5_name_map, &index);
		if (!slot || slot->len == 0 || slot->len > 63 || slot->len > name_len)
			continue;
		len = slot->len;
		if (len == name_len) {
			for (pos = 0; pos < 63; pos++) {
				if (pos >= len)
					break;
				if (name[pos] != slot->bytes[pos])
					same = 0;
			}
			if (same) {
				matched = 1;
				best = len;
			}
			continue;
		}
		if (name[name_len - len - 1] != '.')
			continue;
		same = 1;
		for (pos = 0; pos < 63; pos++) {
			if (pos >= len)
				break;
			if (slot->bytes[pos] == '.')
				suffix = 1;
			if (name[name_len - len + pos] != slot->bytes[pos])
				same = 0;
		}
		if (same && suffix && len >= best) {
			matched = 1;
			best = len;
		}
	}
	if (!matched)
		return T5_DNS_NAME_NOT_ALLOWED;
	if (name_len > best) {
		__u32 left_end = name_len - best - 1;
		__u32 left = 0;
		__u32 pos;

		/* Dots between left-hand labels are not octets. */
		for (pos = 0; pos < 95; pos++) {
			if (pos >= left_end)
				break;
			if (name[pos] != '.')
				left++;
		}
		if (left > cfg->max_label)
			return T5_DNS_LABEL_TOO_LONG;
		if (left >= cfg->entropy_min_length && cfg->entropy_min_length > 0)
			*entropy = 1;
	}
	return T5_POLICY_PERMITS;
}

static __always_inline int parse_name(struct t5_skb *skb, __u32 dns_off, __u8 *name, __u32 *name_len, __u32 *reason, __u32 max_label)
{
	__u32 cursor = dns_off + 12;
	__u32 steps = 0;
	__u32 hops = 0;
	int jumped = 0;
	__u32 labels = 0;

	*name_len = 0;
	*reason = T5_DNS_UNPARSABLE;
	if (cursor > 300)
		return -1;
	while (steps < 16) {
		__u8 length;
		__u8 index;

		steps++;
		if (read8(skb, cursor, &length) < 0)
			return -1;
		if (length == 0)
			return 0;
		if ((length & 0xc0) == 0xc0) {
			__u8 next;
			__u32 pointer;

			if (hops >= 4) {
				*reason = T5_DNS_PARSE_BUDGET;
				return -1;
			}
			if (read8(skb, cursor + 1, &next) < 0)
				return -1;
			pointer = ((length & 0x3fu) << 8) | next;
			if (pointer >= cursor) {
				*reason = T5_DNS_UNPARSABLE;
				return -1;
			}
			jumped = 1;
			cursor = pointer;
			hops++;
			continue;
		}
		if ((length & 0xc0) || length > 63) {
			*reason = T5_DNS_UNPARSABLE;
			return -1;
		}
		if (labels >= 8 || length > max_label) {
			*reason = length > max_label ? T5_DNS_LABEL_TOO_LONG : T5_DNS_PARSE_BUDGET;
			return -1;
		}
		if (*name_len && *name_len < 95)
			name[(*name_len)++] = '.';
		for (index = 0; index < 63; index++) {
			__u8 ch;

			if (index >= length)
				break;
			if (read8(skb, cursor + 1 + index, &ch) < 0)
				return -1;
			if (!ldh(ch)) {
				*reason = T5_DNS_LABEL_NOT_LDH;
				return -1;
			}
			if (*name_len >= 95) {
				*reason = T5_DNS_PARSE_BUDGET;
				return -1;
			}
			name[(*name_len)++] = (__u8)fold_byte(ch);
		}
		labels++;
		cursor += 1u + length;
		(void)jumped;
	}
	*reason = T5_DNS_PARSE_BUDGET;
	return -1;
}

static __always_inline int dns_udp(struct t5_skb *skb, struct t5_cfg *cfg, __u32 dest, __u16 dport)
{
	__u8 qd0;
	__u8 qd1;
	__u8 name[96] = {};
	__u32 name_len = 0;
	__u32 reason = T5_DNS_UNPARSABLE;
	__u32 entropy = 0;
	int failed = 0;
	int over;
	int listed;

	if (read8(skb, 28 + 4, &qd0) < 0 || read8(skb, 28 + 5, &qd1) < 0)
		return finish(cfg, T5_DNS_UNPARSABLE, T5_EVAL, 0, dport, 17);
	if (qd0 != 0 || qd1 != 1)
		return finish(cfg, T5_DNS_QDCOUNT, T5_EVAL, 0, dport, 17);
	if (parse_name(skb, 28, name, &name_len, &reason, cfg->max_label) < 0) {
		__u32 kind = reason == T5_DNS_LABEL_TOO_LONG ? T5_CLASSIFIED : T5_EVAL;

		return finish(cfg, reason, kind, 0, dport, 17);
	}
	over = volume_over(cfg, &failed);
	if (failed)
		return finish(cfg, T5_DNS_QUERY_VOLUME, T5_EVAL, 0, dport, 17);
	listed = addr_listed(&t5_resolver_map, cfg->n_resolvers, dest);
	if (ipv4_link_local(dest))
		return finish(cfg, T5_LINK_LOCAL_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, 17);
	if (!listed)
		return finish(cfg, T5_RESOLVER_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, 17);
	reason = (__u32)name_verdict(cfg, name, name_len, &entropy);
	if (reason != T5_POLICY_PERMITS) {
		__u32 kind = reason == T5_DNS_NAME_NOT_ALLOWED || reason == T5_DNS_LABEL_TOO_LONG ? T5_CLASSIFIED : T5_EVAL;

		return finish(cfg, reason, kind, 0, dport, 17);
	}
	if (over)
		return finish(cfg, T5_DNS_QUERY_VOLUME, T5_CLASSIFIED, entropy, dport, 17);
	return finish(cfg, T5_POLICY_PERMITS, T5_PASS, entropy, dport, 17);
}

static __always_inline int icmp4(struct t5_skb *skb, struct t5_cfg *cfg, __u32 dest)
{
	__u8 kind;

	if (read8(skb, 20, &kind) < 0)
		return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, 1);
	if (ipv4_link_local(dest))
		return finish(cfg, T5_LINK_LOCAL_NOT_ALLOWED, T5_CLASSIFIED, 0, 0, 1);
	if (kind != 0 && kind != 8)
		return finish(cfg, T5_ICMP_TYPE_NOT_ALLOWED, T5_CLASSIFIED, 0, 0, 1);
	if (!addr_listed(&t5_icmp_map, cfg->n_icmp, dest))
		return finish(cfg, T5_ICMP_DESTINATION_NOT_ALLOWED, T5_CLASSIFIED, 0, 0, 1);
	return finish(cfg, T5_POLICY_PERMITS, T5_PASS, 0, 0, 1);
}

static __always_inline int loopback_packet(struct t5_cfg *cfg, __u32 dest, __u16 dport, __u8 proto)
{
	if (ipv4_link_local(dest))
		return finish(cfg, T5_LINK_LOCAL_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, proto);
	if (!ipv4_loopback(dest))
		return finish(cfg, T5_CASE_NOT_APPLICABLE, T5_SCOPE, 0, dport, proto);
	if (port_listed(cfg, dport))
		return finish(cfg, T5_POLICY_PERMITS, T5_PASS, 0, dport, proto);
	return finish(cfg, T5_LOOPBACK_PORT_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, proto);
}

SEC("cgroup_skb/egress")
int t5_cgroup_skb_egress(struct t5_skb *skb)
{
	__u32 zero = 0;
	struct t5_cfg *cfg = bpf_map_lookup_elem(&t5_cfg_map, &zero);
	__u8 vihl = 0;
	__u8 protocol = 0;
	__u8 a0 = 0;
	__u8 a1 = 0;
	__u8 a2 = 0;
	__u8 a3 = 0;
	__u8 p0 = 0;
	__u8 p1 = 0;
	__u32 dest;
	__u16 dport;
	__u8 ihl;

	if (!cfg_ok(cfg))
		return finish(cfg, T5_POLICY_MALFORMED, T5_EVAL, 0, 0, 0);
	if (read8(skb, 0, &vihl) < 0)
		return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, 0);
	if ((vihl >> 4) == 6) {
		__u8 next = 0;

		if (read8(skb, 6, &next) < 0)
			return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, 0);
		if (next == 58)
			return finish(cfg, T5_ICMP_TYPE_NOT_ALLOWED, T5_CLASSIFIED, 0, 0, 58);
		/* Extension headers are not walked. That is fail-closed. */
		return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, next);
	}
	if ((vihl >> 4) != 4)
		return finish(cfg, T5_ADDRESS_NOT_CANONICAL, T5_EVAL, 0, 0, 0);
	ihl = vihl & 0x0f;
	if (ihl != 5)
		return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, 0);
	if (read8(skb, 9, &protocol) < 0)
		return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, 0);
	if (read8(skb, 16, &a0) < 0 || read8(skb, 17, &a1) < 0 || read8(skb, 18, &a2) < 0 || read8(skb, 19, &a3) < 0)
		return finish(cfg, T5_ICMP_HEADER_UNREADABLE, T5_EVAL, 0, 0, protocol);
	dest = ((__u32)a0 << 24) | ((__u32)a1 << 16) | ((__u32)a2 << 8) | a3;
	if (protocol == 1)
		return icmp4(skb, cfg, dest);
	if (protocol != 6 && protocol != 17)
		return finish(cfg, T5_CASE_NOT_APPLICABLE, T5_SCOPE, 0, 0, protocol);
	if (read8(skb, 22, &p0) < 0 || read8(skb, 23, &p1) < 0)
		return finish(cfg, T5_LOOPBACK_HEADER_UNREADABLE, T5_EVAL, 0, 0, protocol);
	dport = ((__u16)p0 << 8) | p1;
	if (protocol == 6 && dport == 53)
		return finish(cfg, T5_DNS_TRANSPORT_NOT_VISIBLE, T5_EVAL, 0, dport, protocol);
	if (protocol == 17 && dport == 53)
		return dns_udp(skb, cfg, dest, dport);
	if (protocol == 6 && dport == 80)
		return finish(cfg, T5_GET_METHOD_NOT_VISIBLE, T5_EVAL, 0, dport, protocol);
	return loopback_packet(cfg, dest, dport, protocol);
}

static __always_inline int connect_v4(struct t5_sock_addr *ctx)
{
	__u32 zero = 0;
	struct t5_cfg *cfg = bpf_map_lookup_elem(&t5_cfg_map, &zero);
	__u32 dest = bswap32(ctx->user_ip4);
	__u16 dport = bswap16((__u16)ctx->user_port);
	__u32 proto = ctx->protocol;

	if (!cfg_ok(cfg))
		return finish(cfg, T5_POLICY_MALFORMED, T5_EVAL, 0, dport, (__u8)proto);
	if (proto != 6 && proto != 17)
		return finish(cfg, T5_LOOPBACK_HEADER_UNREADABLE, T5_EVAL, 0, dport, (__u8)proto);
	if (dport == 53 && addr_listed(&t5_resolver_map, cfg->n_resolvers, dest))
		return finish(cfg, T5_POLICY_PERMITS, T5_PASS, 0, dport, (__u8)proto);
	if (ipv4_link_local(dest))
		return finish(cfg, T5_LINK_LOCAL_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	if (ipv4_loopback(dest)) {
		if (port_listed(cfg, dport))
			return finish(cfg, T5_POLICY_PERMITS, T5_PASS, 0, dport, (__u8)proto);
		return finish(cfg, T5_LOOPBACK_PORT_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	}
	if (dport == 53)
		return finish(cfg, T5_RESOLVER_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	return finish(cfg, T5_CASE_NOT_APPLICABLE, T5_SCOPE, 0, dport, (__u8)proto);
}

SEC("cgroup/connect4")
int t5_connect4(struct t5_sock_addr *ctx)
{
	return connect_v4(ctx);
}

static __always_inline int ipv6_link_local(__u32 first)
{
	return (first & 0xffc00000u) == 0xfe800000u;
}

SEC("cgroup/connect6")
int t5_connect6(struct t5_sock_addr *ctx)
{
	__u32 zero = 0;
	struct t5_cfg *cfg = bpf_map_lookup_elem(&t5_cfg_map, &zero);
	__u32 w0 = bswap32(ctx->user_ip6[0]);
	__u32 w1 = bswap32(ctx->user_ip6[1]);
	__u32 w2 = bswap32(ctx->user_ip6[2]);
	__u32 w3 = bswap32(ctx->user_ip6[3]);
	__u16 dport = bswap16((__u16)ctx->user_port);
	__u32 proto = ctx->protocol;
	int mapped;
	int loopback;

	if (!cfg_ok(cfg))
		return finish(cfg, T5_POLICY_MALFORMED, T5_EVAL, 0, dport, (__u8)proto);
	if (proto != 6 && proto != 17)
		return finish(cfg, T5_LOOPBACK_HEADER_UNREADABLE, T5_EVAL, 0, dport, (__u8)proto);
	if (ipv6_link_local(w0))
		return finish(cfg, T5_LINK_LOCAL_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	mapped = w0 == 0 && w1 == 0 && w2 == 0x0000ffffu;
	loopback = (w0 | w1 | w2 | w3) == 0 || (w0 == 0 && w1 == 0 && w2 == 0 && w3 == 1) || (mapped && ipv4_loopback(w3));
	if (mapped && ipv4_link_local(w3))
		return finish(cfg, T5_LINK_LOCAL_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	if (dport == 53 && mapped && addr_listed(&t5_resolver_map, cfg->n_resolvers, w3))
		return finish(cfg, T5_POLICY_PERMITS, T5_PASS, 0, dport, (__u8)proto);
	if (loopback) {
		if (port_listed(cfg, dport))
			return finish(cfg, T5_POLICY_PERMITS, T5_PASS, 0, dport, (__u8)proto);
		return finish(cfg, T5_LOOPBACK_PORT_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	}
	if (dport == 53)
		return finish(cfg, T5_RESOLVER_NOT_ALLOWED, T5_CLASSIFIED, 0, dport, (__u8)proto);
	return finish(cfg, T5_CASE_NOT_APPLICABLE, T5_SCOPE, 0, dport, (__u8)proto);
}

char LICENSE[] SEC("license") = "GPL";
