import {Route} from "react-router";
import React, {Component, useEffect, useState} from "react";
import {
    API_ACCESS_TOKEN_KEY,
    API_USER_INFO_KEY,
    API_USER_INFO_USERNAME_KEY,
    AUTH_APP_SIGN_IN_URL_PATH
} from "./constants";
import {AUTH_APP_URL} from "../config";
import Cookies from 'js-cookie';
import {getElectionById, getTallySheetById} from "../services/tabulation-api";
import Error from "../components/error";
import Processing from "../components/processing";
import {MessagesConsumer} from "../services/messages.provider"

export function getAuthAppSignInUrl() {
    return `${AUTH_APP_URL}${AUTH_APP_SIGN_IN_URL_PATH}`;
}

export function getAccessToken() {
    const tabulationAccessToken = Cookies.get(API_ACCESS_TOKEN_KEY);

    return tabulationAccessToken;
}

export function getUserInfo() {
    let userInfo = Cookies.get(API_USER_INFO_KEY)
    if (userInfo !== undefined) {
        try {
            userInfo = JSON.parse(userInfo);
        } catch (error) {
            console.log(error.stack);
            userInfo = {};
        }
    } else {
        userInfo = {};
    }

    return userInfo
}

export function getUserName() {
    const userInfo = getUserInfo();
    return userInfo[API_USER_INFO_USERNAME_KEY]
}

export function hasValidToken() {
    const tabulationAccessToken = getAccessToken();
    if (tabulationAccessToken) {
        return true;
    } else {
        return false;
    }
}

export function redirectToLogin() {
    window.location.href = getAuthAppSignInUrl();
}

export function logout() {

    //TODO: notify api to revoke access token

    Cookies.remove('userinfo');
    Cookies.remove('tabulation_access_token');

    window.location.reload();
}


export class ProtectedRoute extends Component {
    constructor(props) {
        super(props)
    }

    static isAuthenticated() {
        return hasValidToken()
    }

    render() {
        if (!ProtectedRoute.isAuthenticated()) {
            redirectToLogin();
            return null;
        } else {
            return <Route
                {...this.props}
                component={(props) => {
                    return <MessagesConsumer>
                        {(messages) => {
                            return <this.props.component {...props} messages={messages}/>
                        }}

                    </MessagesConsumer>
                }}
            />
        }

    }
}

function LoadElectionAndThen(props) {
    const {then, electionId} = props;
    const [processing, setProcessing] = useState(true);
    const [error, setError] = useState(false);
    const [election, setElection] = useState(null);

    const fetchData = async () => {
        try {
            const election = await getElectionById(electionId);

            setElection(election);
        } catch (error) {
            console.log(error.stack);
            setError(true);
        }

        setProcessing(false);
    };

    useEffect(() => {
        fetchData();
    }, []);

    if (processing) {
        return <div className="page">
            <div className="page-content">
                <Processing/>
            </div>
        </div>
    } else if (error) {
        return <Error
            title={"Election not found"}
        />
    } else {
        return then({election});
    }
}

function LoadTallySheetAndThen(props) {
    const {then, electionId, tallySheetId} = props;
    const [processing, setProcessing] = useState(true);
    const [error, setError] = useState(false);
    const [election, setElection] = useState(null);
    const [tallySheet, setTallySheet] = useState(null);

    const fetchData = async () => {
        try {
            const _tallySheet = await getTallySheetById(tallySheetId);
            const _election = await getElectionById(_tallySheet.electionId);
            setTallySheet(_tallySheet);
            setElection(_election);
        } catch (error) {
            console.log(error.stack);
            setError(true);
        }
        setProcessing(false);
    }

    useEffect(() => {
        fetchData()
    }, []);

    if (processing) {
        return <div className="page">
            <div className="page-content">
                <Processing/>
            </div>
        </div>
    } else if (error) {
        return <Error
            title={"Tally sheet not found"}
        />
    } else {
        return then(election, tallySheet);
    }
}

export class ElectionProtectedRoute extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return <ProtectedRoute
            {...this.props}
            component={(props) => {
                let {electionId} = props.match.params;
                const queryString = getQueryStringObject(this.props.location.search);
                if (!electionId) {
                    electionId = queryString.electionId;
                }
                return <LoadElectionAndThen
                    electionId={electionId}
                    then={(electionProps) => {
                        return <this.props.component
                            {...props}
                            {...electionProps}
                            queryString={queryString}
                        />
                    }}
                />
            }}
        />
    }
}

export class TallySheetProtectedRoute extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return <ProtectedRoute
            {...this.props}
            component={(props) => {
                const {tallySheetId} = props.match.params;
                return <LoadTallySheetAndThen
                    tallySheetId={tallySheetId}
                    then={(election, tallySheet) => {
                        return <this.props.component
                            {...props}
                            election={election}
                            tallySheet={tallySheet}
                            queryString={getQueryStringObject(this.props.location.search)}
                        />
                    }}
                />
            }}
        />
    }
}

function getQueryStringObject(queryString) {
    let regex = /\.*[?&]([a-zA-Z0-9]*)=([^?=&]*)/g;
    let result;
    let queryStringObj = {};
    do {
        result = regex.exec(queryString);
        if (result) {
            queryStringObj[result[1]] = result[2];
        }
    } while (result);

    return queryStringObj;
}
