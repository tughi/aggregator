/** @jsx React.DOM */

var EntryMixin = {
	formatDate: function (date) {
		var date = moment(date);
	    var now = moment();
	    if (now.year() != date.year()) {
	    	return date.format("MMM DD YYYY");
	    }
	    if (now.date() == date.date() && now.month() == date.month()) {
	    	return date.format("hh:mm a");
	    }
		return date.format("MMM DD");
	}
};

var ClosedEntry = React.createClass({
	mixins: [EntryMixin],
	render: function () {
		return (
		    <div className={'entry' + (this.props.active ? ' active' : '')}>
		        <div id="header">
		            <div id="title-wrapper">
		                <span id="title">{this.props.entry.title}</span>
		            </div>
		            <div id="date-wrapper">
		                <span id="fadeout"></span><span id="date">{this.formatDate(this.props.entry.updated)}</span>
		            </div>
		            <div id="toggle"></div>
		            <a id="favicon" target="_blank" href={this.props.entry.link} style={{'background-image': 'url("' + this.props.entry.feed.favicon + '")'}}></a>
		            <span id="star"></span>
		        </div>
		    </div>
		);
	}
});

var OpenedEntry = React.createClass({
	mixins: [EntryMixin],
	render: function () {
		return (
		    <div className={'entry open' + (this.props.active ? ' active' : '')}>
		        <div id="body">
		            <div id="content">
		                <div id="content-header">
		                    <h1><a id="title">{this.props.entry.title}</a></h1>
		                    <div>
		                        <span id="author-container">by <span id="author"></span>,</span>
		                        <a id="feed"></a>
		                        <span id="date-container">on <span id="date">{this.formatDate(this.props.entry.updated)}</span></span>
		                        <span id="star" onclick="javascript: return false"></span>
		                    </div>
		                    <div id="tags">
		                        <div id="arrow"></div><div id="toggle-read">keep </div><div id="toggle">close</div>
		                    </div>
		                </div>
		            </div>
		            <div id="footer">
		            </div>
		        </div>
		    </div>
		);
	}
});

var Session = React.createClass({
	getInitialState: function () {
		return {
			active: -1,
			opened: -1,
			entries: [],
			data: {
				feeds: {}, 
				entries: []
			}
		};
	},
	componentWillMount: function () {
		$.ajax({
			url: this.props.url,
			dataType: 'json',
			success: function (data) {
				this.setState({data: data});

				if (data.entries.length) {
					// fetch first page
					this.fetchNextPage();
				}
			}.bind(this)
		});
	},
	fetchNextPage: function () {
		var ids = this.state.data.entries;
		var entries = this.state.entries;

		if (ids.length > entries.length) {
			this.waitNextPage = true;
			$.ajax({
				url: 'api/entries',
				data: {ids: ids.slice(entries.length, entries.length + 50).join(',')},
				success: function (data) {
					// add feed data
					data.map(function (entry) {
						entry.feed = this.state.data.feeds[entry.feed_id];
					}.bind(this));

					// update entries state
					this.setState({entries: this.state.entries.concat(data)});

					this.waitNextPage = false;
				}.bind(this)
			});
		}
	},
	handleScroll: function (event) {
		if (!this.waitNextPage) {
			var content = event.target;
			if (content.scrollHeight - content.scrollTop - content.offsetHeight < 600) {
				this.fetchNextPage();
			}
		}
	},
	handleKeyDown: function (event) {
		var nextActive = Math.min(this.state.active + 1, this.state.entries.length - 1);
		var prevActive = Math.max(this.state.active - 1, 0);
		console.log(event.which);
		switch (event.which) {
		case 74: // j
			this.setState({active: nextActive, opened: nextActive});
			break;
		case 75: // k
			this.setState({active: prevActive, opened: prevActive});
			break;
		case 78: // n
			this.setState({active: nextActive});
			break;
		case 79: // o
			// toggle opened
			this.setState({opened: this.state.opened === this.state.active ? -1 : this.state.active});
			break;
		case 80: // p
			this.setState({active: prevActive});
			break;
		}
	},
	render: function () {
		var entryNodes = this.state.entries.map(function (entry, index) {
			if (index === this.state.opened) {
				return <OpenedEntry key={entry.id} ref={index} entry={entry} active={index === this.state.active} />;
			}
			return <ClosedEntry key={entry.id} ref={index} entry={entry} active={index === this.state.active} />;
		}.bind(this));

		return (
			<div id="content" ref="content" onScroll={this.handleScroll} onKeyDown={this.handleKeyDown}>
				<div id="entries">
					{entryNodes}
				</div>
			</div>
		);
	}
});

$("body").addClass(navigator.userAgent.match(/Android|iPhone|iPad|iPod/i) ? "mobile" : "desktop");

React.renderComponent(<Session url="reader/session" />, document.body);
